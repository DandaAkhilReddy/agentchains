"""Scanner routes — document upload, OCR progress, confirmation."""

import math
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
from app.db.repositories.scan_repo import ScanJobRepository
from app.db.repositories.loan_repo import LoanRepository
from app.db.repositories.user_repo import UserRepository
from app.services.blob_service import BlobService
from app.services.scanner_service import ScannerService
from app.schemas.scanner import UploadResponse, ScanStatusResponse, ConfirmScanRequest, ExtractedField

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

CURRENCY_TO_COUNTRY = {"INR": "IN", "USD": "US"}
COUNTRY_DEFAULTS = {
    "IN": {"rate": 8.5, "tenure": 240},
    "US": {"rate": 6.5, "tenure": 360},
}


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document for OCR scanning."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not supported. Use PDF, PNG, or JPG.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")

    # Upload to local storage
    blob_service = BlobService()
    if not blob_service.is_configured:
        raise HTTPException(status_code=503, detail="Document scanning is temporarily unavailable (storage not configured)")
    blob_url = await blob_service.upload_file(
        content=content,
        filename=file.filename or "document",
        content_type=file.content_type,
        user_id=str(user.id),
    )

    # Create scan job
    repo = ScanJobRepository(db)
    job = await repo.create(
        user_id=user.id,
        blob_url=blob_url,
        original_filename=file.filename or "document",
        file_size_bytes=len(content),
        mime_type=file.content_type,
    )

    # Trigger OCR and auto-create loan
    created_loan_id = None
    detected_country = None
    scan_error = None
    try:
        await repo.update_status(job.id, user.id, "processing")
        scanner = ScannerService()
        fields = []

        # Strategy 1: GPT-4o Vision (images) / GPT-4o text analysis (PDFs via pdfplumber)
        try:
            fields = await scanner.analyze_with_ai(content, file.content_type)
        except Exception as e:
            logger.warning(f"Strategy 1 (AI vision) failed: {e}")

        # Strategy 2: pdfplumber text → GPT-4o text analysis (fallback for images)
        if not fields and scanner.ai_client:
            try:
                ocr_text = await scanner._extract_text(content, file.content_type)
                if ocr_text.strip():
                    fields = await scanner.analyze_text_with_ai(ocr_text)
            except Exception as e:
                logger.warning(f"Strategy 2 (AI text) failed: {e}")

        # Strategy 3: pdfplumber text → regex patterns (final fallback)
        if not fields:
            try:
                extracted_text = await scanner._extract_text(content, file.content_type)
                if extracted_text.strip():
                    fields = scanner._extract_fields(extracted_text, country=user.country)
            except Exception as e:
                logger.warning(f"Strategy 3 (regex) failed: {e}")

        # Propagate meaningful error if all strategies failed
        if not fields:
            scan_error = "Could not extract loan details. Try a clearer photo or enter details manually."

        extracted = {f.field_name: f.value for f in fields}
        confidences = {f.field_name: f.confidence for f in fields}

        # Resolve detected currency → country
        detected_currency = extracted.pop("detected_currency", "") or extracted.pop("currency", "")
        confidences.pop("detected_currency", None)
        confidences.pop("currency", None)
        detected_country = CURRENCY_TO_COUNTRY.get(detected_currency)
        effective_country = detected_country or user.country

        # Auto-create loan from extracted fields with country-aware defaults
        if fields:
            defaults = COUNTRY_DEFAULTS.get(effective_country, COUNTRY_DEFAULTS["IN"])
            principal = float((extracted.get("principal_amount", "0") or "0").replace(",", "")) or 0
            rate = float(extracted.get("interest_rate", "0") or "0") or defaults["rate"]
            tenure = int(extracted.get("tenure_months", "0") or "0") or defaults["tenure"]
            emi = float((extracted.get("emi_amount", "0") or "0").replace(",", "")) or 0
            loan_type = extracted.get("loan_type", "personal")

            # Cross-field validation
            if principal > 0 and emi > 0 and emi > principal:
                logger.warning(f"Validation: EMI ({emi}) > principal ({principal}), swapping")
                principal, emi = emi, principal
            if rate > 50:
                logger.warning(f"Validation: rate {rate}% seems too high, using default")
                rate = defaults["rate"]
            if principal > 0 and emi > 0 and principal < emi * 3:
                logger.warning(f"Validation: principal ({principal}) < 3x EMI ({emi}), suspicious extraction")

            # Auto-calculate EMI if missing but principal is available
            if principal > 0 and emi == 0:
                r = rate / 12 / 100  # monthly rate
                if r > 0:
                    emi = principal * r * math.pow(1 + r, tenure) / (math.pow(1 + r, tenure) - 1)
                else:
                    emi = principal / tenure

            # Auto-infer tax deductions from loan type and country
            eligible_80c = loan_type == "home" and effective_country == "IN"
            eligible_24b = loan_type == "home" and effective_country == "IN"
            eligible_80e = loan_type == "education" and effective_country == "IN"
            eligible_mortgage_deduction = loan_type == "home" and effective_country == "US"
            eligible_student_loan_deduction = loan_type == "education" and effective_country == "US"

            if principal > 0:
                loan_repo = LoanRepository(db)
                loan = await loan_repo.create(
                    user_id=user.id,
                    bank_name=extracted.get("bank_name", "Unknown Bank"),
                    loan_type=loan_type,
                    principal_amount=principal,
                    outstanding_principal=principal,
                    interest_rate=rate,
                    interest_rate_type="floating",
                    tenure_months=tenure,
                    remaining_tenure_months=tenure,
                    emi_amount=round(emi, 2),
                    eligible_80c=eligible_80c,
                    eligible_24b=eligible_24b,
                    eligible_80e=eligible_80e,
                    eligible_mortgage_deduction=eligible_mortgage_deduction,
                    eligible_student_loan_deduction=eligible_student_loan_deduction,
                    source="scan",
                    source_scan_id=job.id,
                )
                created_loan_id = loan.id

        # Auto-switch user country if document currency differs
        if detected_country and detected_country != user.country:
            user_repo = UserRepository(db)
            await user_repo.update(user.id, country=detected_country)
            logger.info(f"Auto-switched user {user.id} country from {user.country} to {detected_country}")

        await repo.update_status(
            job.id,
            user.id,
            "completed" if fields else "review_needed",
            extracted_fields=extracted,
            confidence_scores=confidences,
            created_loan_id=created_loan_id,
        )
    except Exception as e:
        scan_error = str(e)
        await repo.update_status(job.id, user.id, "failed", error_message=scan_error)

    return UploadResponse(
        job_id=job.id,
        loan_id=str(created_loan_id) if created_loan_id else None,
        detected_country=detected_country,
        error=scan_error,
    )


@router.get("/status/{job_id}", response_model=ScanStatusResponse)
async def get_scan_status(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check OCR processing status."""
    repo = ScanJobRepository(db)
    job = await repo.get_by_id(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    extracted_fields = None
    if job.extracted_fields:
        confidences = job.confidence_scores or {}
        extracted_fields = [
            ExtractedField(
                field_name=k,
                value=str(v),
                confidence=confidences.get(k, 0.0),
            )
            for k, v in job.extracted_fields.items()
        ]

    return ScanStatusResponse(
        job_id=job.id,
        status=job.status,
        extracted_fields=extracted_fields,
        error_message=job.error_message,
        processing_time_ms=job.processing_time_ms,
        created_at=job.created_at,
    )


@router.post("/{job_id}/confirm")
async def confirm_scan(
    job_id: UUID,
    data: ConfirmScanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm extracted fields and create loan."""
    scan_repo = ScanJobRepository(db)
    job = await scan_repo.get_by_id(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    loan_repo = LoanRepository(db)
    loan = await loan_repo.create(
        user_id=user.id,
        bank_name=data.bank_name,
        loan_type=data.loan_type,
        principal_amount=data.principal_amount,
        outstanding_principal=data.outstanding_principal,
        interest_rate=data.interest_rate,
        interest_rate_type=data.interest_rate_type,
        tenure_months=data.tenure_months,
        remaining_tenure_months=data.remaining_tenure_months,
        emi_amount=data.emi_amount,
        emi_due_date=data.emi_due_date,
        source="scan",
        source_scan_id=job.id,
    )

    await scan_repo.update_status(job.id, user.id, "completed", created_loan_id=loan.id)

    return {"loan_id": str(loan.id), "message": "Loan created from scan"}

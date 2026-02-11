"""Document scanner: GPT-4o Vision (primary) + pdfplumber text + regex (fallback).

Primary: Sends images directly to GPT-4o-mini Vision for structured extraction.
Fallback: pdfplumber extracts text from PDFs → GPT-4o-mini analyzes text.
Final fallback: regex patterns on extracted text.
"""

import re
import json
import time
import base64
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# ---------- GPT-4o Vision prompts ----------

EXTRACTION_SYSTEM_PROMPT = """You are a document analysis AI that extracts loan/financial details from documents.
Extract loan information and return a JSON object with these fields:
- bank_name: The bank or financial institution name (e.g., "SBI", "HDFC", "Chase", "Wells Fargo")
- loan_type: One of: home, personal, car, education, gold, credit_card, business (best guess)
- principal_amount: The original loan principal or "Amount Financed" as a plain number string (e.g., "2500000").
  For US Truth-in-Lending documents, use the "Amount Financed" field.
  This is typically the LARGEST dollar amount — NOT monthly payments, fees, finance charges, or insurance.
  Look for labels: "Amount Financed", "Loan Amount", "Principal Amount", "Sanctioned Amount".
- interest_rate: Annual interest rate as a number string (e.g., "8.5").
  NOT the APR — prefer "Interest Rate", "Rate of Interest", or "Note Rate" over APR if both appear.
- emi_amount: Monthly payment as a plain number string (e.g., "21000").
  Look for "Monthly Payment", "EMI", "Installment Amount", "Payment Amount".
  This is the recurring monthly amount, NOT the total of all payments.
- tenure_months: Loan tenure in months as a number string (e.g., "240"). Convert years to months if needed.
- account_number: Loan or account number if visible
- currency: The currency in the document. "INR" for ₹/Rupees/Indian currency. "USD" for $/Dollars/US currency. "" if unknown.

Rules:
- Return "" (empty string) for any field you cannot find in the document.
- Only return values you are confident about from the document content.
- Remove currency symbols (₹, $, etc.) and commas from amounts.
- If the document is not a loan/financial document, return empty strings for all fields.
- Always return valid JSON."""

EXTRACTION_USER_PROMPT = "Extract all loan and financial details from this document."


@dataclass
class ExtractedField:
    field_name: str
    value: str
    confidence: float


# ---------- Indian patterns ----------

PATTERNS_IN = {
    "principal": [
        r"(?:loan|principal|sanctioned)\s*(?:amount|amt)?\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{2})?)",
        r"₹\s*([\d,]+(?:\.\d{2})?)\s*(?:lakhs?|lacs?|crores?)?",
    ],
    "interest_rate": [
        r"(?:rate\s*of\s*interest|roi|interest\s*rate)\s*[:\-]?\s*([\d]+\.?\d*)\s*%",
        r"([\d]+\.?\d*)\s*%\s*(?:p\.?a\.?|per\s*annum)",
    ],
    "emi_amount": [
        r"(?:emi|equated\s*monthly\s*installment)\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{2})?)",
        r"monthly\s*(?:installment|payment)\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{2})?)",
    ],
    "tenure": [
        r"(?:tenure|term|period)\s*[:\-]?\s*(\d+)\s*(?:months?|yrs?|years?)",
        r"(\d+)\s*(?:months?|yrs?|years?)\s*(?:tenure|term)",
    ],
    "bank_name": [
        r"(state\s*bank\s*of\s*india|sbi)",
        r"(hdfc\s*(?:bank|ltd)?)",
        r"(icici\s*(?:bank|ltd)?)",
        r"(axis\s*(?:bank|ltd)?)",
        r"(punjab\s*national\s*bank|pnb)",
        r"(bank\s*of\s*baroda|bob)",
        r"(kotak\s*mahindra\s*(?:bank)?)",
        r"(canara\s*bank)",
        r"(union\s*bank)",
        r"(bajaj\s*(?:finance|finserv))",
    ],
    "loan_type": [
        r"(home\s*loan|housing\s*loan|mortgage)",
        r"(personal\s*loan|consumer\s*loan)",
        r"(car\s*loan|auto\s*loan|vehicle\s*loan)",
        r"(education\s*loan|student\s*loan)",
        r"(gold\s*loan)",
        r"(credit\s*card)",
    ],
    "account_number": [
        r"(?:a/c|account|loan)\s*(?:no|number|#)\s*[:\-]?\s*(\d{10,20})",
    ],
}

BANK_NORMALIZER_IN = {
    "state bank of india": "SBI", "sbi": "SBI",
    "hdfc bank": "HDFC", "hdfc ltd": "HDFC", "hdfc": "HDFC",
    "icici bank": "ICICI", "icici ltd": "ICICI", "icici": "ICICI",
    "axis bank": "AXIS", "axis ltd": "AXIS", "axis": "AXIS",
    "punjab national bank": "PNB", "pnb": "PNB",
    "bank of baroda": "BOB", "bob": "BOB",
    "kotak mahindra bank": "KOTAK", "kotak mahindra": "KOTAK", "kotak": "KOTAK",
    "canara bank": "CANARA",
    "union bank": "UNION",
    "bajaj finance": "BAJAJ", "bajaj finserv": "BAJAJ",
}

# ---------- US patterns ----------

PATTERNS_US = {
    "principal": [
        r"(?:loan|principal|original)\s*(?:amount|balance)?\s*[:\-]?\s*\$?\s*([\d,]+(?:\.\d{2})?)",
        r"\$\s*([\d,]+(?:\.\d{2})?)",
    ],
    "interest_rate": [
        r"(?:interest\s*rate|apr|rate)\s*[:\-]?\s*([\d]+\.?\d*)\s*%",
        r"([\d]+\.?\d*)\s*%\s*(?:apr|annual|per\s*(?:year|annum))",
    ],
    "emi_amount": [
        r"(?:monthly\s*payment|payment\s*amount|installment)\s*[:\-]?\s*\$?\s*([\d,]+(?:\.\d{2})?)",
    ],
    "tenure": [
        r"(?:term|tenure|period|duration)\s*[:\-]?\s*(\d+)\s*(?:months?|yrs?|years?)",
        r"(\d+)\s*(?:year|yr)\s*(?:term|mortgage|loan)",
    ],
    "bank_name": [
        r"(chase|jpmorgan\s*chase)",
        r"(bank\s*of\s*america|bofa|boa)",
        r"(wells\s*fargo)",
        r"(citi(?:bank)?)",
        r"(u\.?s\.?\s*bank)",
        r"(pnc\s*(?:bank|financial)?)",
        r"(capital\s*one)",
        r"(td\s*bank)",
        r"(ally\s*(?:bank|financial)?)",
        r"(sofi)",
    ],
    "loan_type": [
        r"(home\s*loan|mortgage|housing\s*loan)",
        r"(personal\s*loan|consumer\s*loan)",
        r"(car\s*loan|auto\s*loan|vehicle\s*loan)",
        r"(education\s*loan|student\s*loan)",
        r"(business\s*loan|sba\s*loan|commercial\s*loan)",
        r"(credit\s*card)",
    ],
    "account_number": [
        r"(?:account|loan)\s*(?:no|number|#)\s*[:\-]?\s*(\d{8,20})",
    ],
}

BANK_NORMALIZER_US = {
    "chase": "Chase", "jpmorgan chase": "Chase",
    "bank of america": "Bank of America", "bofa": "Bank of America", "boa": "Bank of America",
    "wells fargo": "Wells Fargo",
    "citi": "Citi", "citibank": "Citi",
    "u.s. bank": "US Bank", "us bank": "US Bank",
    "pnc": "PNC", "pnc bank": "PNC", "pnc financial": "PNC",
    "capital one": "Capital One",
    "td bank": "TD Bank",
    "ally": "Ally", "ally bank": "Ally", "ally financial": "Ally",
    "sofi": "SoFi",
}

LOAN_TYPE_NORMALIZER = {
    "home loan": "home", "housing loan": "home", "mortgage": "home",
    "personal loan": "personal", "consumer loan": "personal",
    "car loan": "car", "auto loan": "car", "vehicle loan": "car",
    "education loan": "education", "student loan": "education",
    "gold loan": "gold",
    "credit card": "credit_card",
    "business loan": "business", "sba loan": "business", "commercial loan": "business",
}


def _clean_amount(value: str) -> str:
    """Remove commas and normalize amount string."""
    return value.replace(",", "").strip()


def _extract_with_patterns(text: str, field: str, patterns: dict) -> tuple[str, float]:
    """Try all patterns for a field, return (value, confidence)."""
    field_patterns = patterns.get(field, [])
    for pattern in field_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value, 0.85
    return "", 0.0


def _detect_currency_from_text(text: str) -> str:
    """Detect currency from document text. Returns 'INR', 'USD', or ''."""
    inr_signals = len(re.findall(r"₹|\bRs\.?\b|\bINR\b|\brupees?\b|\blakhs?\b|\blacs?\b|\bcrores?\b", text, re.IGNORECASE))
    usd_signals = len(re.findall(r"\$|\bUSD\b|\bdollars?\b", text, re.IGNORECASE))

    if inr_signals > usd_signals and inr_signals >= 1:
        return "INR"
    if usd_signals > inr_signals and usd_signals >= 1:
        return "USD"
    return ""


class ScannerService:
    """Document scanner: GPT-4o Vision (primary) + pdfplumber + regex (fallback)."""

    def __init__(self):
        if settings.openai_api_key:
            self.ai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            self.ai_client = None
            logger.warning("OpenAI not configured — AI extraction unavailable")

    # ---------- Primary: GPT-4o Vision extraction ----------

    async def analyze_with_ai(self, content: bytes, content_type: str) -> list[ExtractedField]:
        """Use GPT-4o Vision to extract loan fields from any document."""
        if not self.ai_client:
            raise RuntimeError("OpenAI not configured")

        start_time = time.time()

        if content_type in ("image/png", "image/jpeg", "image/jpg"):
            # Images: send directly to GPT-4o vision as base64
            b64 = base64.b64encode(content).decode("utf-8")
            messages = [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": EXTRACTION_USER_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{content_type};base64,{b64}",
                    }},
                ]},
            ]
        else:
            # PDFs: extract text with pdfplumber, then send text to GPT-4o
            text = await self._extract_text(content, content_type)
            if not text.strip():
                logger.warning("No text extracted from PDF")
                return []
            messages = [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"{EXTRACTION_USER_PROMPT}\n\nDocument text:\n{text[:4000]}"},
            ]

        # response_format is NOT supported with vision (image_url) inputs
        kwargs = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 500,
        }
        if content_type not in ("image/png", "image/jpeg", "image/jpg"):
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.ai_client.chat.completions.create(**kwargs)

        raw = response.choices[0].message.content or "{}"
        fields = self._parse_ai_response(raw)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"AI extraction completed in {elapsed_ms}ms, extracted {len(fields)} fields")
        logger.info(f"AI extracted fields: {[(f.field_name, f.value) for f in fields]}")
        return fields

    def _parse_ai_response(self, raw: str) -> list[ExtractedField]:
        """Parse GPT-4o response into ExtractedField list.

        Robust: tries direct JSON parse → code block extraction → brace extraction.
        """
        logger.info(f"Raw AI response: {raw[:500]}")
        data = None

        # 1. Direct JSON parse
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Extract from ```json ... ``` code block
        if data is None:
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass

        # 3. Find first { ... } in the response
        if data is None:
            m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass

        if not data or not isinstance(data, dict):
            logger.error(f"Failed to parse AI response: {raw[:300]}")
            return []

        field_keys = [
            "bank_name", "loan_type", "principal_amount",
            "interest_rate", "emi_amount", "tenure_months", "account_number",
            "currency",
        ]

        fields = []
        for key in field_keys:
            value = str(data.get(key, "")).strip()
            if value:
                if key in ("principal_amount", "emi_amount"):
                    value = re.sub(r"[₹$,\s]", "", value)
                if key == "interest_rate":
                    value = value.replace("%", "").strip()
                fields.append(ExtractedField(key, value, 0.90))
        return fields

    async def analyze_text_with_ai(self, text: str) -> list[ExtractedField]:
        """Send extracted text to GPT-4o for structured extraction (no vision)."""
        if not self.ai_client:
            raise RuntimeError("OpenAI not configured")

        start_time = time.time()
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"{EXTRACTION_USER_PROMPT}\n\nDocument text:\n{text[:4000]}"},
        ]
        response = await self.ai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        fields = self._parse_ai_response(raw)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"AI text extraction completed in {elapsed_ms}ms, extracted {len(fields)} fields")
        return fields

    async def _extract_text(self, content: bytes, content_type: str) -> str:
        """Extract raw text from a PDF using pdfplumber."""
        if content_type != "application/pdf":
            return ""
        try:
            import io
            import pdfplumber
            text_parts = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text_parts.append(page_text)
                    # Also extract table text
                    for table in page.extract_tables():
                        for row in table:
                            text_parts.append(" ".join(cell or "" for cell in row))
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"pdfplumber extraction error: {e}")
            return ""

    @staticmethod
    def _run_patterns(text: str, patterns: dict, bank_normalizer: dict) -> list[ExtractedField]:
        """Run a single set of regex patterns against text."""
        fields: list[ExtractedField] = []

        bank_raw, bank_conf = _extract_with_patterns(text, "bank_name", patterns)
        if bank_raw:
            normalized = bank_normalizer.get(bank_raw.lower(), bank_raw.upper())
            fields.append(ExtractedField("bank_name", normalized, bank_conf))

        type_raw, type_conf = _extract_with_patterns(text, "loan_type", patterns)
        if type_raw:
            normalized = LOAN_TYPE_NORMALIZER.get(type_raw.lower(), "personal")
            fields.append(ExtractedField("loan_type", normalized, type_conf))

        principal_raw, principal_conf = _extract_with_patterns(text, "principal", patterns)
        if principal_raw:
            fields.append(ExtractedField("principal_amount", _clean_amount(principal_raw), principal_conf))

        rate_raw, rate_conf = _extract_with_patterns(text, "interest_rate", patterns)
        if rate_raw:
            fields.append(ExtractedField("interest_rate", rate_raw, rate_conf))

        emi_raw, emi_conf = _extract_with_patterns(text, "emi_amount", patterns)
        if emi_raw:
            fields.append(ExtractedField("emi_amount", _clean_amount(emi_raw), emi_conf))

        tenure_raw, tenure_conf = _extract_with_patterns(text, "tenure", patterns)
        if tenure_raw:
            fields.append(ExtractedField("tenure_months", tenure_raw, tenure_conf))

        acc_raw, acc_conf = _extract_with_patterns(text, "account_number", patterns)
        if acc_raw:
            fields.append(ExtractedField("account_number", acc_raw, acc_conf))

        return fields

    def _extract_fields(self, text: str, country: str = "IN") -> list[ExtractedField]:
        """Extract loan-related fields from document text with auto currency detection.

        Tries the primary pattern set (based on country), then the alternate set.
        Uses whichever found more fields (prefers primary on tie).
        Also detects currency from text and appends as a field.
        """
        primary_patterns = PATTERNS_IN if country == "IN" else PATTERNS_US
        primary_normalizer = BANK_NORMALIZER_IN if country == "IN" else BANK_NORMALIZER_US
        alt_patterns = PATTERNS_US if country == "IN" else PATTERNS_IN
        alt_normalizer = BANK_NORMALIZER_US if country == "IN" else BANK_NORMALIZER_IN

        primary_fields = self._run_patterns(text, primary_patterns, primary_normalizer)
        alt_fields = self._run_patterns(text, alt_patterns, alt_normalizer)

        # Use whichever found more data (prefer primary on tie)
        fields = primary_fields if len(primary_fields) >= len(alt_fields) else alt_fields

        # Detect currency and append as a field
        currency = _detect_currency_from_text(text)
        if currency:
            fields.append(ExtractedField("detected_currency", currency, 0.80))

        return fields

"""Invoice service: generation, PDF creation, payment marking, voiding, and retrieval."""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.billing import Invoice

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


async def generate_invoice(
    db: AsyncSession,
    agent_id: str,
    subscription_id: str,
    line_items: list[dict],
    due_date: datetime | None = None,
) -> Invoice:
    """Generate a new invoice for an agent.

    Args:
        db: Async database session.
        agent_id: The agent being billed.
        subscription_id: The subscription this invoice is associated with.
        line_items: List of dicts, each with 'description', 'amount', and optionally 'quantity'.
        due_date: Optional due date; defaults to 30 days from now.
    """
    amount = sum(item.get("amount", 0) * item.get("quantity", 1) for item in line_items)
    tax = round(amount * 0.0, 4)  # Tax calculation placeholder (0% default)
    total = round(amount + tax, 4)

    invoice = Invoice(
        agent_id=agent_id,
        subscription_id=subscription_id,
        amount_usd=amount,
        tax_usd=tax,
        total_usd=total,
        status="open",
        line_items_json=json.dumps(line_items),
        due_at=due_date or (_utcnow() + timedelta(days=30)),
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def mark_invoice_paid(
    db: AsyncSession,
    invoice_id: str,
    stripe_invoice_id: str | None = None,
) -> Invoice:
    """Mark an invoice as paid."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    invoice.status = "paid"
    invoice.paid_at = _utcnow()
    if stripe_invoice_id:
        invoice.stripe_invoice_id = stripe_invoice_id

    await db.commit()
    await db.refresh(invoice)
    return invoice


async def void_invoice(db: AsyncSession, invoice_id: str) -> Invoice:
    """Void an invoice (cannot be voided if already paid)."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    if invoice.status == "paid":
        raise ValueError("Cannot void a paid invoice")

    invoice.status = "void"
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def get_invoice(db: AsyncSession, invoice_id: str) -> Invoice | None:
    """Get a single invoice by ID."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# PDF generation (text-based)
# ---------------------------------------------------------------------------

_INVOICE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "invoices")


def _ensure_invoice_dir() -> str:
    """Ensure the invoice output directory exists and return its path."""
    abs_dir = os.path.abspath(_INVOICE_DIR)
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir


def _render_invoice_text(invoice: Invoice) -> str:
    """Render an invoice as a plain-text document."""
    line_items = []
    if invoice.line_items_json:
        try:
            line_items = json.loads(invoice.line_items_json)
        except (json.JSONDecodeError, TypeError):
            line_items = []

    lines = [
        "=" * 60,
        "                      INVOICE",
        "=" * 60,
        "",
        f"  Invoice ID:      {invoice.id}",
        f"  Agent ID:        {invoice.agent_id}",
        f"  Status:          {invoice.status}",
        f"  Issued At:       {invoice.issued_at.isoformat() if invoice.issued_at else 'N/A'}",
        f"  Due At:          {invoice.due_at.isoformat() if invoice.due_at else 'N/A'}",
        f"  Paid At:         {invoice.paid_at.isoformat() if invoice.paid_at else 'N/A'}",
        "",
        "-" * 60,
        "  LINE ITEMS",
        "-" * 60,
    ]

    for i, item in enumerate(line_items, start=1):
        desc = item.get("description", "")
        amount = item.get("amount", 0)
        qty = item.get("quantity", 1)
        lines.append(f"  {i}. {desc}")
        lines.append(f"     Amount: ${amount:.4f}  x  Qty: {qty}")
        lines.append("")

    lines.extend([
        "-" * 60,
        f"  Subtotal:        ${float(invoice.amount_usd):.4f}",
        f"  Tax:             ${float(invoice.tax_usd):.4f}",
        f"  TOTAL:           ${float(invoice.total_usd):.4f}",
        "=" * 60,
        "",
        "  Stripe Invoice:  " + (invoice.stripe_invoice_id or "N/A"),
        "",
        "  Thank you for using AgentChains!",
        "=" * 60,
    ])

    return "\n".join(lines)


async def generate_invoice_pdf(db: AsyncSession, invoice_id: str) -> str:
    """Generate a text-based invoice 'PDF' and return the file path.

    Since we avoid external PDF libraries, this creates a .txt file that
    represents the invoice in a human-readable format. In production this
    would be uploaded to Azure Blob Storage and a URL returned.

    Returns the local file path where the invoice was written.
    """
    invoice = await get_invoice(db, invoice_id)
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    invoice_dir = _ensure_invoice_dir()
    filename = f"invoice_{invoice.id}.txt"
    filepath = os.path.join(invoice_dir, filename)

    content = _render_invoice_text(invoice)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Update the invoice's pdf_url field
    invoice.pdf_url = filepath
    await db.commit()
    await db.refresh(invoice)

    logger.info("Generated invoice PDF at '%s' for invoice '%s'", filepath, invoice_id)
    return filepath


async def get_invoice_pdf_url(db: AsyncSession, invoice_id: str) -> str | None:
    """Return the PDF URL/path for an invoice, or None if not yet generated."""
    invoice = await get_invoice(db, invoice_id)
    if not invoice:
        return None
    return invoice.pdf_url if invoice.pdf_url else None

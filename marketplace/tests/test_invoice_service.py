"""Tests for invoice_service.py."""

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services.invoice_service import (
    InvoiceService, _ensure_invoice_dir, _render_invoice_text,
    generate_invoice, generate_invoice_pdf, get_invoice,
    get_invoice_pdf_url, mark_invoice_paid, void_invoice,
)
from marketplace.models.billing import Invoice


async def _mksub(db, agent_id):
    import uuid
    from marketplace.models.billing import BillingPlan, Subscription
    plan = BillingPlan(id=str(uuid.uuid4()), name=f"tp-{uuid.uuid4().hex[:6]}", tier="starter", price_usd_monthly=Decimal("0"))
    db.add(plan); await db.commit(); await db.refresh(plan)
    sub = Subscription(id=str(uuid.uuid4()), agent_id=agent_id, plan_id=plan.id, status="active")
    db.add(sub); await db.commit(); await db.refresh(sub)
    return sub.id


class TestGenInvoice:
    async def test_basic(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        items = [{"description": "API", "amount": 5.0, "quantity": 2}, {"description": "S", "amount": 3.0}]
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=items)
        assert inv.status == "open" and float(inv.amount_usd) == 13.0

    async def test_json(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "C", "amount": 10.0}])
        assert json.loads(inv.line_items_json)[0]["description"] == "C"

    async def test_due_default(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        t = datetime.now(timezone.utc).replace(tzinfo=None)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[])
        due = inv.due_at.replace(tzinfo=None) if inv.due_at.tzinfo else inv.due_at
        assert due >= t + timedelta(days=29, hours=23)

    async def test_due_custom(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        d = datetime(2026, 6, 15, tzinfo=timezone.utc)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[], due_date=d)
        due = inv.due_at.replace(tzinfo=None) if inv.due_at and inv.due_at.tzinfo else inv.due_at
        assert due == d.replace(tzinfo=None)

    async def test_empty(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[])
        assert float(inv.amount_usd) == 0.0

    async def test_qty1(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "S", "amount": 7.5}])
        assert float(inv.amount_usd) == 7.5

    async def test_no_amt(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "N"}])
        assert float(inv.amount_usd) == 0.0


class TestMarkPaid:
    async def test_ok(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        p = await mark_invoice_paid(db, inv.id)
        assert p.status == "paid" and p.paid_at is not None

    async def test_stripe(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        p = await mark_invoice_paid(db, inv.id, stripe_invoice_id="in_abc")
        assert p.stripe_invoice_id == "in_abc"

    async def test_404(self, db):
        with pytest.raises(ValueError, match="not found"):
            await mark_invoice_paid(db, "bad")


class TestVoid:
    async def test_open(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        assert (await void_invoice(db, inv.id)).status == "void"

    async def test_paid(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        await mark_invoice_paid(db, inv.id)
        with pytest.raises(ValueError, match="Cannot void a paid invoice"):
            await void_invoice(db, inv.id)

    async def test_404(self, db):
        with pytest.raises(ValueError, match="not found"):
            await void_invoice(db, "bad")


class TestGetInv:
    async def test_ok(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        c = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[])
        f = await get_invoice(db, c.id)
        assert f is not None and f.id == c.id

    async def test_none(self, db):
        assert await get_invoice(db, "no") is None


class TestRender:
    def test_basic(self):
        inv = Invoice(id="i1", agent_id="a1", amount_usd=Decimal("10"), tax_usd=Decimal("0"), total_usd=Decimal("10"), status="open", line_items_json=json.dumps([{"description": "API", "amount": 10.0}]))
        assert "INVOICE" in _render_invoice_text(inv)

    def test_empty(self):
        inv = Invoice(id="i2", agent_id="a2", amount_usd=Decimal("0"), tax_usd=Decimal("0"), total_usd=Decimal("0"), status="open", line_items_json="[]")
        assert "INVOICE" in _render_invoice_text(inv)

    def test_none_json(self):
        inv = Invoice(id="i3", agent_id="a3", amount_usd=Decimal("5"), tax_usd=Decimal("0"), total_usd=Decimal("5"), status="paid", line_items_json=None)
        assert "INVOICE" in _render_invoice_text(inv)

    def test_bad_json(self):
        inv = Invoice(id="i4", agent_id="a4", amount_usd=Decimal("5"), tax_usd=Decimal("0"), total_usd=Decimal("5"), status="open", line_items_json="bad")
        assert "INVOICE" in _render_invoice_text(inv)

    def test_stripe(self):
        inv = Invoice(id="i5", agent_id="a5", amount_usd=Decimal("10"), tax_usd=Decimal("0"), total_usd=Decimal("10"), status="paid", stripe_invoice_id="in_s", line_items_json="[]")
        assert "in_s" in _render_invoice_text(inv)

    def test_na(self):
        inv = Invoice(id="i6", agent_id="a6", amount_usd=Decimal("10"), tax_usd=Decimal("0"), total_usd=Decimal("10"), status="open", stripe_invoice_id=None, line_items_json="[]")
        assert "N/A" in _render_invoice_text(inv)


class TestDir:
    def test_abs(self): assert os.path.isabs(_ensure_invoice_dir())
    def test_exists(self): assert os.path.isdir(_ensure_invoice_dir())


class TestPdf:
    async def test_gen(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "T", "amount": 5.0}])
        fp = await generate_invoice_pdf(db, inv.id)
        assert os.path.isfile(fp)
        with open(fp, "r") as f: assert "INVOICE" in f.read()
        os.remove(fp)

    async def test_url(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[])
        fp = await generate_invoice_pdf(db, inv.id)
        r = await get_invoice(db, inv.id)
        assert r.pdf_url == fp
        if os.path.isfile(fp): os.remove(fp)

    async def test_404(self, db):
        with pytest.raises(ValueError, match="not found"):
            await generate_invoice_pdf(db, "bad")


class TestPdfUrl:
    async def test_none(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[])
        assert await get_invoice_pdf_url(db, inv.id) is None

    async def test_after(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        fp = await generate_invoice_pdf(db, inv.id)
        assert await get_invoice_pdf_url(db, inv.id) == fp
        if os.path.isfile(fp): os.remove(fp)

    async def test_miss(self, db):
        assert await get_invoice_pdf_url(db, "nope") is None


class TestSvc:
    async def test_gen(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await InvoiceService().generate(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "W", "amount": 2.0}])
        assert inv.status == "open"

    async def test_pay(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        assert (await InvoiceService().mark_paid(db, inv.id)).status == "paid"

    async def test_void(self, db, make_agent):
        a, _ = await make_agent()
        s = await _mksub(db, a.id)
        inv = await generate_invoice(db, agent_id=a.id, subscription_id=s, line_items=[{"description": "x", "amount": 1.0}])
        assert (await InvoiceService().void(db, inv.id)).status == "void"
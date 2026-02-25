"""Addendum tests for deposit_service.py: get_deposits, authorization, edge cases."""

from decimal import Decimal

import pytest

from marketplace.core.exceptions import AuthorizationError, NotFoundError
from marketplace.services.deposit_service import (
    cancel_deposit,
    confirm_deposit,
    create_deposit,
    get_deposits,
)


class TestGetDeposits:
    async def test_empty(self, db, make_agent):
        a, _ = await make_agent()
        deposits, total = await get_deposits(db, a.id)
        assert deposits == []
        assert total == 0

    async def test_single(self, db, make_agent):
        a, _ = await make_agent()
        await create_deposit(db, a.id, 10.0)
        deposits, total = await get_deposits(db, a.id)
        assert total == 1
        assert deposits[0]["amount_usd"] == 10.0

    async def test_pagination(self, db, make_agent):
        a, _ = await make_agent()
        for i in range(5):
            await create_deposit(db, a.id, float(i + 1))
        deposits, total = await get_deposits(db, a.id, page=1, page_size=2)
        assert total == 5
        assert len(deposits) == 2

    async def test_page2(self, db, make_agent):
        a, _ = await make_agent()
        for i in range(5):
            await create_deposit(db, a.id, float(i + 1))
        deposits, total = await get_deposits(db, a.id, page=2, page_size=2)
        assert total == 5
        assert len(deposits) == 2

    async def test_fields(self, db, make_agent):
        a, _ = await make_agent()
        await create_deposit(db, a.id, 25.0, payment_method="stripe")
        deposits, _ = await get_deposits(db, a.id)
        d = deposits[0]
        assert d["agent_id"] == a.id
        assert d["payment_method"] == "stripe"
        assert d["status"] == "pending"
        assert d["currency"] == "USD"
        assert "id" in d
        assert "created_at" in d


class TestDepositAuth:
    async def test_confirm_wrong_agent(self, db, make_agent):
        a, _ = await make_agent()
        dep = await create_deposit(db, a.id, 10.0)
        with pytest.raises(AuthorizationError):
            await confirm_deposit(db, dep["id"], agent_id="wrong-agent")

    async def test_cancel_wrong_agent(self, db, make_agent):
        a, _ = await make_agent()
        dep = await create_deposit(db, a.id, 10.0)
        with pytest.raises(AuthorizationError):
            await cancel_deposit(db, dep["id"], agent_id="wrong-agent")

    async def test_confirm_allows_none_agent(self, db, make_agent, make_token_account, seed_platform):
        a, _ = await make_agent()
        await make_token_account(a.id, 0)
        dep = await create_deposit(db, a.id, 5.0)
        result = await confirm_deposit(db, dep["id"], agent_id=None)
        assert result["status"] == "completed"


class TestDepositEdgeCases:
    async def test_zero_amount(self, db, make_agent):
        a, _ = await make_agent()
        with pytest.raises(ValueError, match="positive"):
            await create_deposit(db, a.id, 0)

    async def test_negative_amount(self, db, make_agent):
        a, _ = await make_agent()
        with pytest.raises(ValueError, match="positive"):
            await create_deposit(db, a.id, -5.0)

    async def test_decimal_amount(self, db, make_agent):
        a, _ = await make_agent()
        dep = await create_deposit(db, a.id, Decimal("12.34"))
        assert dep["amount_usd"] == 12.34

    async def test_confirm_not_found(self, db):
        with pytest.raises(NotFoundError):
            await confirm_deposit(db, "nonexistent")

    async def test_cancel_not_found(self, db):
        with pytest.raises(NotFoundError):
            await cancel_deposit(db, "nonexistent")

    async def test_double_confirm(self, db, make_agent, make_token_account, seed_platform):
        a, _ = await make_agent()
        await make_token_account(a.id, 0)
        dep = await create_deposit(db, a.id, 10.0)
        await confirm_deposit(db, dep["id"])
        with pytest.raises(ValueError, match="completed"):
            await confirm_deposit(db, dep["id"])

    async def test_cancel_after_confirm(self, db, make_agent, make_token_account, seed_platform):
        a, _ = await make_agent()
        await make_token_account(a.id, 0)
        dep = await create_deposit(db, a.id, 10.0)
        await confirm_deposit(db, dep["id"])
        with pytest.raises(ValueError, match="completed"):
            await cancel_deposit(db, dep["id"])


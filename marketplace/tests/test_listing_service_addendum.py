"""Addendum tests for listing_service.py: listing_to_response_dict and get_listing_content."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.services.listing_service import (
    get_listing_content,
    listing_to_response_dict,
)


def _fake_listing(**overrides):
    """Build a fake listing object with sensible defaults."""
    defaults = dict(
        id="lst-1",
        seller_id="s1",
        seller=SimpleNamespace(id="s1", name="Seller One"),
        title="T",
        description="D",
        category="finance",
        content_hash="abc",
        content_size=100,
        content_type="text/csv",
        price_usdc=9.99,
        currency="USD",
        metadata_json=json.dumps({"k": "v"}),
        tags=json.dumps(["a", "b"]),
        quality_score=0.8,
        freshness_at=None,
        expires_at=None,
        status="active",
        trust_status="pending_verification",
        trust_score=0,
        verification_summary_json="{}",
        provenance_json="{}",
        access_count=5,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestListingToResponseDict:
    @patch("marketplace.services.listing_service.trust_verification_service")
    def test_basic(self, mock_tvs):
        mock_tvs.build_trust_payload.return_value = {
            "trust_status": "verified_secure_data",
            "trust_score": 85,
            "verification_summary": {},
            "provenance": {},
        }
        lst = _fake_listing()
        d = listing_to_response_dict(lst)
        assert d["id"] == "lst-1"
        assert d["seller"] == {"id": "s1", "name": "Seller One"}
        assert d["metadata"] == {"k": "v"}
        assert d["tags"] == ["a", "b"]
        assert d["price_usd"] == 9.99
        assert d["trust_status"] == "verified_secure_data"

    @patch("marketplace.services.listing_service.trust_verification_service")
    def test_no_seller(self, mock_tvs):
        mock_tvs.build_trust_payload.return_value = {
            "trust_status": "pending_verification",
            "trust_score": 0,
            "verification_summary": {},
            "provenance": {},
        }
        lst = _fake_listing(seller=None)
        d = listing_to_response_dict(lst)
        assert d["seller"] is None

    @patch("marketplace.services.listing_service.trust_verification_service")
    def test_metadata_already_dict(self, mock_tvs):
        mock_tvs.build_trust_payload.return_value = {
            "trust_status": "pending_verification",
            "trust_score": 0,
            "verification_summary": {},
            "provenance": {},
        }
        lst = _fake_listing(metadata_json={"already": "dict"}, tags=["x"])
        d = listing_to_response_dict(lst)
        assert d["metadata"] == {"already": "dict"}
        assert d["tags"] == ["x"]

    @patch("marketplace.services.listing_service.trust_verification_service")
    def test_null_quality(self, mock_tvs):
        mock_tvs.build_trust_payload.return_value = {
            "trust_status": "pending_verification",
            "trust_score": 0,
            "verification_summary": {},
            "provenance": {},
        }
        lst = _fake_listing(quality_score=None)
        d = listing_to_response_dict(lst)
        assert d["quality_score"] == 0.5


class TestGetListingContent:
    @patch("marketplace.services.cdn_service.get_content", new_callable=AsyncMock)
    async def test_returns_bytes(self, mock_cdn):
        mock_cdn.return_value = b"hello world"
        result = await get_listing_content("hash123")
        assert result == b"hello world"
        mock_cdn.assert_awaited_once_with("hash123")

    @patch("marketplace.services.cdn_service.get_content", new_callable=AsyncMock)
    async def test_returns_none(self, mock_cdn):
        mock_cdn.return_value = None
        result = await get_listing_content("missing")
        assert result is None


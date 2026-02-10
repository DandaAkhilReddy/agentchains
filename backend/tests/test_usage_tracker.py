"""Tests for the UsageTracker service — cost estimation and usage logging.

Covers:
- estimate_openai_cost: correct calculation, zero tokens, large counts
- estimate_doc_intel_cost: correct per-page calculation
- estimate_blob_cost: returns fixed per-operation cost
- track_usage: successful DB logging, fire-and-forget error handling, correct args
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.usage_tracker import (
    PRICING,
    estimate_blob_cost,
    estimate_doc_intel_cost,
    estimate_openai_cost,
    track_usage,
)


# ---------------------------------------------------------------------------
# estimate_openai_cost
# ---------------------------------------------------------------------------


class TestEstimateOpenaiCost:
    """Tests for the OpenAI token-to-cost estimation function."""

    def test_typical_token_counts(self):
        """A typical request with moderate input/output tokens."""
        tokens_in = 500
        tokens_out = 200
        expected_in = (500 / 1_000_000) * PRICING["openai"]["input_per_1m"]
        expected_out = (200 / 1_000_000) * PRICING["openai"]["output_per_1m"]
        expected = round(expected_in + expected_out, 6)

        result = estimate_openai_cost(tokens_in, tokens_out)
        assert result == expected

    def test_zero_tokens_returns_zero(self):
        """Zero input and output tokens should produce zero cost."""
        result = estimate_openai_cost(0, 0)
        assert result == 0.0

    def test_zero_input_nonzero_output(self):
        """Zero input tokens with some output tokens."""
        result = estimate_openai_cost(0, 1000)
        expected = round((1000 / 1_000_000) * PRICING["openai"]["output_per_1m"], 6)
        assert result == expected

    def test_nonzero_input_zero_output(self):
        """Some input tokens with zero output tokens."""
        result = estimate_openai_cost(1000, 0)
        expected = round((1000 / 1_000_000) * PRICING["openai"]["input_per_1m"], 6)
        assert result == expected

    def test_large_token_counts(self):
        """Large token counts (1M+ tokens) to verify no overflow/precision issues."""
        tokens_in = 2_000_000
        tokens_out = 1_000_000
        expected_in = (2_000_000 / 1_000_000) * PRICING["openai"]["input_per_1m"]
        expected_out = (1_000_000 / 1_000_000) * PRICING["openai"]["output_per_1m"]
        expected = round(expected_in + expected_out, 6)

        result = estimate_openai_cost(tokens_in, tokens_out)
        assert result == expected
        # Sanity check: 2M input @ $0.15/1M = $0.30, 1M output @ $0.60/1M = $0.60
        assert result == 0.9

    def test_exact_1m_tokens(self):
        """Exactly 1M tokens should return the per-1M pricing directly."""
        result_in_only = estimate_openai_cost(1_000_000, 0)
        assert result_in_only == PRICING["openai"]["input_per_1m"]

        result_out_only = estimate_openai_cost(0, 1_000_000)
        assert result_out_only == PRICING["openai"]["output_per_1m"]

    def test_result_is_rounded_to_six_decimals(self):
        """Cost values should be rounded to 6 decimal places."""
        # Use a token count that produces a long decimal
        result = estimate_openai_cost(7, 3)
        # Verify the result has at most 6 decimal places
        result_str = f"{result:.10f}"
        significant = result_str.rstrip("0")
        decimal_part = significant.split(".")[1] if "." in significant else ""
        assert len(decimal_part) <= 6

    def test_known_manual_calculation(self):
        """Hand-verified calculation: 10,000 in + 5,000 out.

        Input cost:  10000 / 1M * 0.15 = 0.0015
        Output cost:  5000 / 1M * 0.60 = 0.003
        Total: 0.0045
        """
        result = estimate_openai_cost(10_000, 5_000)
        assert result == 0.0045


# ---------------------------------------------------------------------------
# estimate_doc_intel_cost
# ---------------------------------------------------------------------------


class TestEstimateDocIntelCost:
    """Tests for the Document Intelligence per-page cost estimation."""

    def test_single_page(self):
        """Default single page cost."""
        result = estimate_doc_intel_cost(1)
        assert result == PRICING["doc_intel"]["per_page"]

    def test_multiple_pages(self):
        """Multi-page document cost scales linearly."""
        result = estimate_doc_intel_cost(10)
        expected = round(10 * PRICING["doc_intel"]["per_page"], 6)
        assert result == expected

    def test_default_is_one_page(self):
        """Calling with no arguments defaults to 1 page."""
        result = estimate_doc_intel_cost()
        assert result == PRICING["doc_intel"]["per_page"]

    def test_zero_pages(self):
        """Zero pages should produce zero cost."""
        result = estimate_doc_intel_cost(0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# estimate_blob_cost
# ---------------------------------------------------------------------------


class TestEstimateBlobCost:
    """Tests for the Blob Storage per-operation cost."""

    def test_returns_fixed_cost(self):
        """Should return the per-operation constant from PRICING."""
        result = estimate_blob_cost()
        assert result == PRICING["blob_storage"]["per_operation"]
        assert result == 0.000001


# ---------------------------------------------------------------------------
# track_usage (async)
# ---------------------------------------------------------------------------


class TestTrackUsage:
    """Tests for the async fire-and-forget usage logger."""

    @pytest.mark.asyncio
    async def test_successful_logging(self, mock_db_session):
        """track_usage should create a UsageLogRepository and call log()."""
        with patch(
            "app.services.usage_tracker.UsageLogRepository"
        ) as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await track_usage(
                db=mock_db_session,
                service="openai",
                operation="chat_completion",
                tokens_input=500,
                tokens_output=200,
                estimated_cost=0.0045,
            )

            # Repository was instantiated with the session
            MockRepo.assert_called_once_with(mock_db_session)
            # log() was called exactly once
            mock_repo_instance.log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_correct_parameters(self, mock_db_session):
        """track_usage passes all arguments through to repo.log()."""
        user_id = uuid.UUID("00000000-0000-4000-a000-000000000001")
        metadata = {"model": "gpt-4o-mini", "endpoint": "/advisor/ask"}

        with patch(
            "app.services.usage_tracker.UsageLogRepository"
        ) as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await track_usage(
                db=mock_db_session,
                service="openai",
                operation="chat_completion",
                user_id=user_id,
                tokens_input=1000,
                tokens_output=500,
                estimated_cost=0.00045,
                metadata=metadata,
            )

            mock_repo_instance.log.assert_awaited_once_with(
                service="openai",
                operation="chat_completion",
                user_id=user_id,
                tokens_input=1000,
                tokens_output=500,
                estimated_cost=0.00045,
                metadata=metadata,
            )

    @pytest.mark.asyncio
    async def test_handles_database_error_gracefully(self, mock_db_session):
        """Database errors should be caught and logged, never raised."""
        with patch(
            "app.services.usage_tracker.UsageLogRepository"
        ) as MockRepo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.log.side_effect = Exception(
                "DB connection lost"
            )
            MockRepo.return_value = mock_repo_instance

            # Should NOT raise — fire-and-forget semantics
            await track_usage(
                db=mock_db_session,
                service="openai",
                operation="chat_completion",
                estimated_cost=0.001,
            )

    @pytest.mark.asyncio
    async def test_logs_warning_on_database_error(self, mock_db_session):
        """When the DB write fails, a warning is logged."""
        with patch(
            "app.services.usage_tracker.UsageLogRepository"
        ) as MockRepo, patch(
            "app.services.usage_tracker.logger"
        ) as mock_logger:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.log.side_effect = RuntimeError("timeout")
            MockRepo.return_value = mock_repo_instance

            await track_usage(
                db=mock_db_session,
                service="openai",
                operation="chat_completion",
            )

            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Failed to log usage" in warning_msg
            assert "timeout" in warning_msg

    @pytest.mark.asyncio
    async def test_default_optional_parameters(self, mock_db_session):
        """Optional parameters default correctly (None/0)."""
        with patch(
            "app.services.usage_tracker.UsageLogRepository"
        ) as MockRepo:
            mock_repo_instance = AsyncMock()
            MockRepo.return_value = mock_repo_instance

            await track_usage(
                db=mock_db_session,
                service="doc_intel",
                operation="scan_document",
            )

            mock_repo_instance.log.assert_awaited_once_with(
                service="doc_intel",
                operation="scan_document",
                user_id=None,
                tokens_input=None,
                tokens_output=None,
                estimated_cost=0,
                metadata=None,
            )

    @pytest.mark.asyncio
    async def test_different_service_and_operation(self, mock_db_session):
        """track_usage correctly forwards various service/operation combos."""
        test_cases = [
            ("doc_intel", "scan_document"),
            ("blob_storage", "upload"),
            ("translator", "translate_text"),
            ("tts", "synthesize_speech"),
        ]

        for service, operation in test_cases:
            with patch(
                "app.services.usage_tracker.UsageLogRepository"
            ) as MockRepo:
                mock_repo_instance = AsyncMock()
                MockRepo.return_value = mock_repo_instance

                await track_usage(
                    db=mock_db_session,
                    service=service,
                    operation=operation,
                    estimated_cost=0.001,
                )

                call_kwargs = mock_repo_instance.log.call_args[1]
                assert call_kwargs["service"] == service
                assert call_kwargs["operation"] == operation

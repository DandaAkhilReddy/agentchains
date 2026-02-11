"""Tests for the EmbeddingService (OpenAI text-embedding-3-small).

Covers:
- Initialization with and without OpenAI API key
- Single embedding generation (success, no client, empty text, API error, model param)
- Batch embedding generation (multiple, single, no client, empty list, API error)
- Knowledge base content validation (count, types, keys, text content)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# TestInit: 2 tests
# ---------------------------------------------------------------------------

class TestInit:
    """Test EmbeddingService __init__ client setup."""

    def test_client_created_when_configured(self):
        """When openai_api_key is present, client should be set (not None)."""
        with patch("app.services.embedding_service.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test-key-123"
            mock_settings.openai_embedding_model = "text-embedding-3-small"

            from app.services.embedding_service import EmbeddingService
            svc = EmbeddingService()

            assert svc.client is not None

    def test_client_none_when_not_configured(self):
        """When openai_api_key is empty, client should be None."""
        with patch("app.services.embedding_service.settings") as mock_settings:
            mock_settings.openai_api_key = ""

            from app.services.embedding_service import EmbeddingService
            svc = EmbeddingService()

            assert svc.client is None


# ---------------------------------------------------------------------------
# TestGenerateEmbedding: 5 tests
# ---------------------------------------------------------------------------

class TestGenerateEmbedding:
    """Test single-text embedding generation."""

    @pytest.mark.asyncio
    async def test_success_returns_1536_floats(self):
        """Successful API call returns a list of 1536 floats."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        fake_embedding = [0.1] * 1536

        mock_item = MagicMock()
        mock_item.embedding = fake_embedding

        mock_response = MagicMock()
        mock_response.data = [mock_item]

        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await svc.generate_embedding("test text")

        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)
        assert result == fake_embedding

    @pytest.mark.asyncio
    async def test_not_configured_returns_zeros(self):
        """When client is None, returns [0.0] * 1536."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        svc.client = None

        result = await svc.generate_embedding("test text")

        assert len(result) == 1536
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_empty_text_returns_1536_dims(self):
        """Even with empty string input, should return 1536 dimensions."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        fake_embedding = [0.5] * 1536

        mock_item = MagicMock()
        mock_item.embedding = fake_embedding

        mock_response = MagicMock()
        mock_response.data = [mock_item]

        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await svc.generate_embedding("")

        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_api_error_returns_zeros(self):
        """When the API raises an exception, returns [0.0] * 1536."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        result = await svc.generate_embedding("test text")

        assert len(result) == 1536
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_model_parameter_is_correct(self):
        """Verify that the configured embedding model is passed in the API call."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        fake_embedding = [0.1] * 1536

        mock_item = MagicMock()
        mock_item.embedding = fake_embedding

        mock_response = MagicMock()
        mock_response.data = [mock_item]

        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(return_value=mock_response)

        await svc.generate_embedding("test text")

        svc.client.embeddings.create.assert_awaited_once_with(
            input="test text",
            model="text-embedding-3-small",
        )


# ---------------------------------------------------------------------------
# TestGenerateEmbeddingsBatch: 5 tests
# ---------------------------------------------------------------------------

class TestGenerateEmbeddingsBatch:
    """Test batch embedding generation."""

    @pytest.mark.asyncio
    async def test_three_texts_returns_three_embeddings(self):
        """3 input texts should produce 3 embedding vectors."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        texts = ["text one", "text two", "text three"]

        mock_items = []
        for i in range(3):
            item = MagicMock()
            item.embedding = [float(i)] * 1536
            mock_items.append(item)

        mock_response = MagicMock()
        mock_response.data = mock_items

        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await svc.generate_embeddings_batch(texts)

        assert len(result) == 3
        assert all(len(emb) == 1536 for emb in result)
        # Verify ordering: first embedding should be all 0.0, second all 1.0, etc.
        assert result[0][0] == 0.0
        assert result[1][0] == 1.0
        assert result[2][0] == 2.0

    @pytest.mark.asyncio
    async def test_single_text_returns_one_embedding(self):
        """1 input text should produce 1 embedding vector."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)

        mock_item = MagicMock()
        mock_item.embedding = [0.42] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_item]

        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await svc.generate_embeddings_batch(["single text"])

        assert len(result) == 1
        assert len(result[0]) == 1536

    @pytest.mark.asyncio
    async def test_not_configured_returns_zeros(self):
        """When client is None, returns zero vectors for each input text."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        svc.client = None

        result = await svc.generate_embeddings_batch(["a", "b", "c"])

        assert len(result) == 3
        for emb in result:
            assert len(emb) == 1536
            assert all(v == 0.0 for v in emb)

    @pytest.mark.asyncio
    async def test_empty_texts_list_returns_empty(self):
        """An empty input list should return an empty list."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        svc.client = None  # doesn't matter; empty list short-circuits

        result = await svc.generate_embeddings_batch([])

        assert result == []

    @pytest.mark.asyncio
    async def test_api_error_returns_zeros(self):
        """When the API raises an exception, returns zero vectors for each text."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService.__new__(EmbeddingService)
        svc.client = MagicMock()
        svc.embedding_model = "text-embedding-3-small"
        svc.client.embeddings = MagicMock()
        svc.client.embeddings.create = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        result = await svc.generate_embeddings_batch(["a", "b"])

        assert len(result) == 2
        for emb in result:
            assert len(emb) == 1536
            assert all(v == 0.0 for v in emb)


# ---------------------------------------------------------------------------
# TestKnowledgeBase: 8 tests
# ---------------------------------------------------------------------------

class TestKnowledgeBase:
    """Test the static KNOWLEDGE_BASE content returned by get_knowledge_base_items."""

    def _get_items(self) -> list[dict]:
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService.__new__(EmbeddingService)
        return svc.get_knowledge_base_items()

    def test_returns_9_items(self):
        """Knowledge base should contain exactly 9 items."""
        items = self._get_items()
        assert len(items) == 9

    def test_has_4_glossary_items(self):
        """Should have 4 glossary items: emi, mclr, repo_rate, cibil."""
        items = self._get_items()
        glossary = [i for i in items if i["source_type"] == "glossary"]
        assert len(glossary) == 4
        glossary_ids = {i["source_id"] for i in glossary}
        assert glossary_ids == {"emi", "mclr", "repo_rate", "cibil"}

    def test_has_2_rbi_guideline_items(self):
        """Should have 2 rbi_guideline items."""
        items = self._get_items()
        rbi = [i for i in items if i["source_type"] == "rbi_guideline"]
        assert len(rbi) == 2

    def test_has_3_tax_rule_items(self):
        """Should have 3 tax_rule items."""
        items = self._get_items()
        tax = [i for i in items if i["source_type"] == "tax_rule"]
        assert len(tax) == 3

    def test_each_item_has_required_keys(self):
        """Every item must have source_type, source_id, and text keys."""
        items = self._get_items()
        required_keys = {"source_type", "source_id", "text"}
        for item in items:
            assert required_keys.issubset(item.keys()), (
                f"Item {item.get('source_id', '?')} missing keys: "
                f"{required_keys - set(item.keys())}"
            )

    def test_emi_text_contains_equated_monthly_installment(self):
        """The EMI glossary entry should mention 'Equated Monthly Installment'."""
        items = self._get_items()
        emi = next(i for i in items if i["source_id"] == "emi")
        assert "Equated Monthly Installment" in emi["text"]

    def test_section_80c_text_contains_150000(self):
        """Section 80C entry should mention the 1,50,000 limit."""
        items = self._get_items()
        s80c = next(i for i in items if i["source_id"] == "section_80c")
        assert "1,50,000" in s80c["text"]

    def test_reducing_balance_text_contains_reducing_balance(self):
        """Reducing balance entry should mention 'Reducing Balance'."""
        items = self._get_items()
        rb = next(i for i in items if i["source_id"] == "reducing_balance")
        assert "Reducing Balance" in rb["text"]

"""Embedding service using OpenAI text-embedding-3-small (1536 dims).

Handles:
- Text chunking for knowledge base
- Embedding generation
- Pre-seeding RBI guidelines, loan glossary, tax rules
"""

import logging
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Knowledge base content to pre-seed
KNOWLEDGE_BASE = [
    {
        "source_type": "glossary",
        "source_id": "emi",
        "text": "EMI (Equated Monthly Installment) is a fixed payment amount made by a borrower to a lender at a specified date each month. EMIs are used to pay off both principal and interest over a set period. In India, most home loans, personal loans, and car loans are repaid through EMIs calculated using the reducing balance method.",
    },
    {
        "source_type": "glossary",
        "source_id": "mclr",
        "text": "MCLR (Marginal Cost of Funds Based Lending Rate) is the minimum interest rate below which banks in India cannot lend. Introduced by RBI in 2016, it replaced the base rate system. Most floating rate loans are linked to MCLR. When MCLR changes, your loan interest rate changes after the reset period (usually 6 months or 1 year).",
    },
    {
        "source_type": "glossary",
        "source_id": "repo_rate",
        "text": "Repo Rate is the rate at which RBI lends money to commercial banks. As of 2024, the repo rate is 6.50%. When RBI cuts the repo rate, banks can borrow cheaper, which often leads to lower loan interest rates for consumers. External Benchmark Linked Loans (EBLR) are directly linked to repo rate.",
    },
    {
        "source_type": "glossary",
        "source_id": "cibil",
        "text": "CIBIL Score (now TransUnion CIBIL) is India's primary credit score ranging from 300-900. A score above 750 is considered good for loan approval. Factors: payment history (30%), credit utilization (25%), credit age (25%), credit mix (10%), credit inquiries (10%). Free annual credit report available at cibil.com.",
    },
    {
        "source_type": "rbi_guideline",
        "source_id": "prepayment_2014",
        "text": "RBI Circular 2014: Banks cannot charge prepayment penalty on floating rate loans (home, personal, car, education). This applies to all scheduled commercial banks. Fixed rate loans may still have foreclosure charges (typically 2-5%). This rule makes it free to make extra payments on most Indian loans.",
    },
    {
        "source_type": "tax_rule",
        "source_id": "section_80c",
        "text": "Section 80C of Income Tax Act: Deduction up to ₹1,50,000 per year on principal repayment of home loans. Also covers: PPF, ELSS, life insurance premiums, tuition fees. The limit is combined across all 80C eligible investments. Available only under Old Tax Regime.",
    },
    {
        "source_type": "tax_rule",
        "source_id": "section_24b",
        "text": "Section 24(b): Deduction on home loan interest. Self-occupied property: up to ₹2,00,000 per year. Let-out property: no upper limit on interest deduction. The property must be completed within 5 years of taking the loan. Available under both Old and New (limited) regimes.",
    },
    {
        "source_type": "tax_rule",
        "source_id": "section_80e",
        "text": "Section 80E: Deduction on education loan interest. No upper limit on the amount. Available for 8 years from the year you start repaying the loan. Loan must be from a recognized financial institution. Covers higher education in India or abroad. Only the interest component is deductible, not principal.",
    },
    {
        "source_type": "rbi_guideline",
        "source_id": "reducing_balance",
        "text": "In India, most bank loans use the Reducing Balance Method for EMI calculation. Interest is calculated on the outstanding principal, which reduces each month as you pay EMIs. This is different from the Flat Rate method (used by some NBFCs) where interest is calculated on the original principal throughout. Always check which method your lender uses — reducing balance is more favorable.",
    },
]


class EmbeddingService:
    """Generate and manage text embeddings using OpenAI."""

    def __init__(self):
        if settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.embedding_model = settings.openai_embedding_model
        else:
            self.client = None
            logger.warning("OpenAI not configured for embeddings")

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a text chunk using text-embedding-3-small."""
        if not self.client:
            return [0.0] * 1536

        try:
            response = await self.client.embeddings.create(
                input=text,
                model=self.embedding_model,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return [0.0] * 1536

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call."""
        if not self.client:
            return [[0.0] * 1536 for _ in texts]

        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=self.embedding_model,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
            return [[0.0] * 1536 for _ in texts]

    def get_knowledge_base_items(self) -> list[dict]:
        """Return pre-defined knowledge base items for seeding."""
        return KNOWLEDGE_BASE

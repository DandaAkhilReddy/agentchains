"""AI insights routes — explanations, RAG Q&A, TTS."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
from app.db.repositories.loan_repo import LoanRepository
from app.db.repositories.embedding_repo import EmbeddingRepository
from app.services.ai_service import AIService
from app.services.embedding_service import EmbeddingService
from app.services.translator_service import TranslatorService
from app.services.tts_service import TTSService
from app.services.usage_tracker import track_usage, estimate_openai_cost

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ExplainLoanRequest(BaseModel):
    loan_id: str


class ExplainStrategyRequest(BaseModel):
    strategy_name: str
    num_loans: int
    extra: float
    interest_saved: float
    months_saved: int
    payoff_order: list[str]


class AskRequest(BaseModel):
    question: str


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


class AIResponse(BaseModel):
    text: str
    language: str


class TTSResponse(BaseModel):
    audio_base64: str | None
    language: str


@router.post("/explain-loan", response_model=AIResponse)
async def explain_loan(
    req: ExplainLoanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI explanation of a loan."""
    from uuid import UUID
    repo = LoanRepository(db)
    loan = await repo.get_by_id(UUID(req.loan_id), user.id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    ai = AIService()
    explanation, usage = await ai.explain_loan(
        bank_name=loan.bank_name,
        loan_type=loan.loan_type,
        principal=float(loan.principal_amount),
        outstanding=float(loan.outstanding_principal),
        rate=float(loan.interest_rate),
        rate_type=loan.interest_rate_type,
        emi=float(loan.emi_amount),
        remaining_months=loan.remaining_tenure_months,
    )
    if usage:
        await track_usage(db, "openai", "chat", user.id,
                          usage.get("prompt_tokens"), usage.get("completion_tokens"),
                          estimate_openai_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))

    # Translate if user prefers non-English
    lang = user.preferred_language
    if lang != "en":
        translator = TranslatorService()
        explanation = await translator.translate(explanation, lang)

    return AIResponse(text=explanation, language=lang)


@router.post("/explain-strategy", response_model=AIResponse)
async def explain_strategy(
    req: ExplainStrategyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI explanation of optimizer strategy."""
    ai = AIService()
    explanation, usage = await ai.explain_strategy(
        strategy_name=req.strategy_name,
        num_loans=req.num_loans,
        extra=req.extra,
        interest_saved=req.interest_saved,
        months_saved=req.months_saved,
        payoff_order=req.payoff_order,
    )
    if usage:
        await track_usage(db, "openai", "chat", user.id,
                          usage.get("prompt_tokens"), usage.get("completion_tokens"),
                          estimate_openai_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))

    lang = user.preferred_language
    if lang != "en":
        translator = TranslatorService()
        explanation = await translator.translate(explanation, lang)

    return AIResponse(text=explanation, language=lang)


@router.post("/ask", response_model=AIResponse)
async def ask(
    req: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """RAG-powered Q&A about loans and RBI rules."""
    embedding_svc = EmbeddingService()
    query_embedding = await embedding_svc.generate_embedding(req.question)

    embed_repo = EmbeddingRepository(db)
    results = await embed_repo.similarity_search(query_embedding, limit=3)
    context_chunks = [r.chunk_text for r in results]

    ai = AIService()
    answer, usage = await ai.ask_with_context(req.question, context_chunks)
    if usage:
        await track_usage(db, "openai", "chat", user.id,
                          usage.get("prompt_tokens"), usage.get("completion_tokens"),
                          estimate_openai_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))

    lang = user.preferred_language
    if lang != "en":
        translator = TranslatorService()
        answer = await translator.translate(answer, lang)

    return AIResponse(text=answer, language=lang)


class ExplainLoansBatchRequest(BaseModel):
    loan_ids: list[str]


class LoanInsight(BaseModel):
    loan_id: str
    text: str


class BatchInsightsResponse(BaseModel):
    insights: list[LoanInsight]
    language: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = []


@router.post("/explain-loans-batch", response_model=BatchInsightsResponse)
async def explain_loans_batch(
    req: ExplainLoansBatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI explanations for multiple loans in parallel."""
    import asyncio
    from uuid import UUID as _UUID

    repo = LoanRepository(db)
    ai = AIService()
    sem = asyncio.Semaphore(5)
    country = user.country or "IN"

    async def explain_one(loan_id_str: str) -> LoanInsight:
        async with sem:
            loan = await repo.get_by_id(_UUID(loan_id_str), user.id)
            if not loan:
                return LoanInsight(loan_id=loan_id_str, text="Loan not found")
            explanation, usage = await ai.explain_loan(
                bank_name=loan.bank_name,
                loan_type=loan.loan_type,
                principal=float(loan.principal_amount),
                outstanding=float(loan.outstanding_principal),
                rate=float(loan.interest_rate),
                rate_type=loan.interest_rate_type,
                emi=float(loan.emi_amount),
                remaining_months=loan.remaining_tenure_months,
                country=country,
            )
            if usage:
                await track_usage(db, "openai", "chat", user.id,
                                  usage.get("prompt_tokens"), usage.get("completion_tokens"),
                                  estimate_openai_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))
            return LoanInsight(loan_id=loan_id_str, text=explanation)

    insights = await asyncio.gather(*[explain_one(lid) for lid in req.loan_ids])

    lang = user.preferred_language
    if lang and lang != "en":
        translator = TranslatorService()
        for insight in insights:
            insight.text = await translator.translate(insight.text, lang)

    return BatchInsightsResponse(insights=list(insights), language=lang or "en")


@router.post("/chat", response_model=AIResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conversational RAG chat with history."""
    embedding_svc = EmbeddingService()
    query_embedding = await embedding_svc.generate_embedding(req.message)

    embed_repo = EmbeddingRepository(db)
    results = await embed_repo.similarity_search(query_embedding, limit=3)
    context_chunks = [r.chunk_text for r in results]

    ai = AIService()
    history = [(m.role, m.content) for m in req.history[-6:]]
    answer, usage = await ai.chat_with_history(
        message=req.message,
        history=history,
        context_chunks=context_chunks,
        country=user.country or "IN",
    )
    if usage:
        await track_usage(db, "openai", "chat", user.id,
                          usage.get("prompt_tokens"), usage.get("completion_tokens"),
                          estimate_openai_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))

    lang = user.preferred_language
    if lang and lang != "en":
        translator = TranslatorService()
        answer = await translator.translate(answer, lang)

    return AIResponse(text=answer, language=lang or "en")


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    req: TTSRequest,
    user: User = Depends(get_current_user),
):
    """Generate TTS audio for AI explanation text."""
    tts = TTSService()
    audio = await tts.generate_audio(req.text, req.language)
    return TTSResponse(audio_base64=audio, language=req.language)

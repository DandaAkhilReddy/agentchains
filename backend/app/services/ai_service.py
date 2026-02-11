"""OpenAI GPT-4o-mini integration for AI insights.

Features:
- Loan explanation in plain language (country-aware)
- Strategy explanation with relay race metaphor
- RAG-powered Q&A (pgvector search + GPT)
"""

import logging
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_IN = """You are a friendly Indian financial advisor who explains loan concepts simply.
Use relatable Indian examples. Mix Hindi/English (Hinglish) where natural.
Always reference amounts in ₹ with Indian numbering (₹1,00,000 not ₹100,000).
Keep explanations under 200 words unless asked for detail.
Never give specific investment advice — only explain loan mechanics and optimization strategies."""

SYSTEM_PROMPT_US = """You are a friendly American financial advisor who explains loan concepts simply.
Use relatable American examples with clear, plain English.
Always reference amounts in $ with US numbering ($100,000).
Mention relevant US concepts like mortgage interest deduction, student loan interest deduction,
standard vs itemized deductions, and filing status where appropriate.
Keep explanations under 200 words unless asked for detail.
Never give specific investment advice — only explain loan mechanics and optimization strategies."""

LOAN_EXPLANATION_PROMPT_IN = """Explain this loan in simple terms that any Indian borrower would understand:

Bank: {bank_name}
Type: {loan_type}
Principal: ₹{principal:,.0f}
Outstanding: ₹{outstanding:,.0f}
Interest Rate: {rate}% ({rate_type})
EMI: ₹{emi:,.0f}
Remaining: {remaining_months} months

Include:
1. How much total interest they'll pay
2. What portion of their EMI goes to interest vs principal right now
3. One actionable tip to save money"""

LOAN_EXPLANATION_PROMPT_US = """Explain this loan in simple terms that any American borrower would understand:

Bank: {bank_name}
Type: {loan_type}
Principal: ${principal:,.0f}
Outstanding: ${outstanding:,.0f}
Interest Rate: {rate}% ({rate_type})
Monthly Payment: ${emi:,.0f}
Remaining: {remaining_months} months

Include:
1. How much total interest they'll pay
2. What portion of their monthly payment goes to interest vs principal right now
3. One actionable tip to save money (mention tax deductions if applicable)"""

STRATEGY_EXPLANATION_PROMPT_IN = """Explain this loan repayment strategy in simple, relatable terms:

Strategy: {strategy_name}
Number of loans: {num_loans}
Extra monthly payment: ₹{extra:,.0f}
Interest saved: ₹{interest_saved:,.0f}
Months saved: {months_saved}
Payoff order: {payoff_order}

Use the "relay race" metaphor: "Jab ek loan khatam hota hai, uski EMI dusre loan pe lagao —
like a relay race where each runner passes the baton!"

Make it motivating and actionable."""

STRATEGY_EXPLANATION_PROMPT_US = """Explain this loan repayment strategy in simple, relatable terms:

Strategy: {strategy_name}
Number of loans: {num_loans}
Extra monthly payment: ${extra:,.0f}
Interest saved: ${interest_saved:,.0f}
Months saved: {months_saved}
Payoff order: {payoff_order}

Use the "relay race" metaphor: when one loan is paid off, roll that payment into the next loan —
like a relay race where each runner passes the baton!

Make it motivating and actionable."""

RAG_QA_PROMPT_IN = """Answer the user's question about Indian loans using ONLY the context below.
If the context doesn't contain the answer, say "I don't have specific information about that,
but here's what I know about Indian loans in general..."

Context from knowledge base:
{context}

User question: {question}

Answer in simple language with Indian context."""

RAG_QA_PROMPT_US = """Answer the user's question about American loans using ONLY the context below.
If the context doesn't contain the answer, say "I don't have specific information about that,
but here's what I know about US loans in general..."

Context from knowledge base:
{context}

User question: {question}

Answer in simple language with American financial context."""


def _get_prompts(country: str) -> tuple[str, str, str, str]:
    """Return (system, loan_explanation, strategy_explanation, rag_qa) prompts for a country."""
    if country == "US":
        return SYSTEM_PROMPT_US, LOAN_EXPLANATION_PROMPT_US, STRATEGY_EXPLANATION_PROMPT_US, RAG_QA_PROMPT_US
    return SYSTEM_PROMPT_IN, LOAN_EXPLANATION_PROMPT_IN, STRATEGY_EXPLANATION_PROMPT_IN, RAG_QA_PROMPT_IN


class AIService:
    """OpenAI service for loan explanations and RAG Q&A."""

    def __init__(self):
        if settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = settings.openai_model
        else:
            self.client = None
            logger.warning("OpenAI not configured — set OPENAI_API_KEY")

    async def _chat(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """Send a chat completion request. Returns (text, usage_dict)."""
        if not self.client:
            return "AI service not configured. Please set your OpenAI API key.", {}

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return response.choices[0].message.content or "", usage
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return f"Sorry, I couldn't generate an explanation right now. Error: {str(e)}", {}

    async def explain_loan(
        self,
        bank_name: str,
        loan_type: str,
        principal: float,
        outstanding: float,
        rate: float,
        rate_type: str,
        emi: float,
        remaining_months: int,
        country: str = "IN",
    ) -> tuple[str, dict]:
        """Generate plain-language loan explanation. Returns (text, usage)."""
        system, loan_tmpl, _, _ = _get_prompts(country)
        prompt = loan_tmpl.format(
            bank_name=bank_name,
            loan_type=loan_type,
            principal=principal,
            outstanding=outstanding,
            rate=rate,
            rate_type=rate_type,
            emi=emi,
            remaining_months=remaining_months,
        )
        return await self._chat(system, prompt)

    async def explain_strategy(
        self,
        strategy_name: str,
        num_loans: int,
        extra: float,
        interest_saved: float,
        months_saved: int,
        payoff_order: list[str],
        country: str = "IN",
    ) -> tuple[str, dict]:
        """Generate strategy explanation. Returns (text, usage)."""
        system, _, strategy_tmpl, _ = _get_prompts(country)
        prompt = strategy_tmpl.format(
            strategy_name=strategy_name,
            num_loans=num_loans,
            extra=extra,
            interest_saved=interest_saved,
            months_saved=months_saved,
            payoff_order=" → ".join(payoff_order),
        )
        return await self._chat(system, prompt)

    async def ask_with_context(self, question: str, context_chunks: list[str], country: str = "IN") -> tuple[str, dict]:
        """RAG-powered Q&A using retrieved context. Returns (text, usage)."""
        system, _, _, rag_tmpl = _get_prompts(country)
        context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No relevant context found."
        prompt = rag_tmpl.format(context=context, question=question)
        return await self._chat(system, prompt)

    async def chat_with_history(
        self,
        message: str,
        history: list[tuple[str, str]],
        context_chunks: list[str],
        country: str = "IN",
    ) -> tuple[str, dict]:
        """Chat with conversation history and RAG context. Returns (text, usage)."""
        if not self.client:
            return "AI service not configured. Please set your OpenAI API key.", {}

        system, _, _, _ = _get_prompts(country)
        context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No specific context available."

        system_with_context = f"""{system}

You also have access to this knowledge base context (use it when relevant):
{context}"""

        messages = [{"role": "system", "content": system_with_context}]
        for role, content in history:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return response.choices[0].message.content or "", usage
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Sorry, I couldn't process your message. Error: {str(e)}", {}

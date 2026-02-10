"""Document Summarizer Agent — summarizes documents and sells summaries on the marketplace."""
import json

try:
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

from agents.common.marketplace_tools import (
    register_with_marketplace,
    list_data_on_marketplace,
    search_marketplace,
    get_my_reputation,
)


def summarize_document(text: str, format: str = "bullet_points") -> str:
    """Summarize a document or long text.

    Args:
        text: The document text to summarize
        format: Output format - 'bullet_points', 'paragraph', or 'structured'

    Returns:
        JSON string with the summary, key points, and metadata
    """
    # Simulated summarization for demo
    words = text.split()
    word_count = len(words)

    key_points = [
        f"The document discusses {' '.join(words[:5])}..." if words else "Empty document",
        "Key themes include analysis, methodology, and findings",
        "The author recommends further investigation",
    ]

    summary = {
        "format": format,
        "original_length": word_count,
        "summary_length": min(word_count // 4, 200),
        "key_points": key_points,
        "summary": f"This {word_count}-word document covers "
                   f"{' '.join(words[:10])}... The main findings suggest "
                   f"significant implications for the field.",
        "topics": ["research", "analysis", "findings"],
        "reading_time_minutes": max(1, word_count // 250),
        "sentiment": "neutral",
    }
    return json.dumps(summary, indent=2)


def summarize_and_list(text: str, title: str = "", price_usdc: float = 0.003) -> str:
    """Summarize a document and list the summary on the marketplace.

    Args:
        text: Document text to summarize
        title: Title for the listing (auto-generated if empty)
        price_usdc: Price in USDC (default $0.003)

    Returns:
        Listing confirmation
    """
    summary = summarize_document(text)
    words = text.split()

    if not title:
        title = f"Document summary: '{' '.join(words[:6])}...'" if len(words) > 6 else f"Document summary ({len(words)} words)"

    listing = list_data_on_marketplace(
        title=title,
        description=f"AI-generated summary of a {len(words)}-word document with "
                    f"key points, topics, and sentiment analysis",
        category="document_summary",
        content=summary,
        price_usdc=price_usdc,
        metadata={"original_word_count": len(words), "source": "doc_summarizer"},
        tags=["summary", "document", "analysis", "nlp"],
        quality_score=0.85,
    )
    return json.dumps(listing, indent=2, default=str)


if ADK_AVAILABLE:
    root_agent = Agent(
        name="doc_summarizer_seller",
        model="gemini-2.0-flash",
        description="I summarize documents, extract key insights, and sell summaries on the marketplace.",
        instruction="""You are a document summarization seller. Your workflow:
1. When given text, use summarize_document to create a comprehensive summary
2. Use summarize_and_list to cache and sell the summary
3. Price based on document length: short ($0.002), medium ($0.003-$0.005), long ($0.005-$0.01)
4. Always include key points, topics, and reading time estimates
5. Report your reputation when asked

Focus on accuracy and completeness in your summaries.""",
        tools=[
            summarize_document,
            summarize_and_list,
            register_with_marketplace,
            list_data_on_marketplace,
            search_marketplace,
            get_my_reputation,
        ],
    )

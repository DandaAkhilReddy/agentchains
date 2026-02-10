"""Code Analyzer Agent — analyzes code, caches insights, and sells them on the marketplace."""
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


def analyze_code(code: str, language: str = "python") -> str:
    """Analyze a code snippet and return structured insights.

    Args:
        code: The source code to analyze
        language: Programming language (python, javascript, etc.)

    Returns:
        JSON string with analysis results: complexity, issues, suggestions
    """
    # Simulated code analysis for demo
    lines = code.strip().split("\n") if code.strip() else []
    analysis = {
        "language": language,
        "lines_of_code": len(lines),
        "complexity": {
            "cyclomatic": min(len(lines) // 5 + 1, 15),
            "cognitive": min(len(lines) // 3 + 1, 20),
            "rating": "A" if len(lines) < 50 else "B" if len(lines) < 200 else "C",
        },
        "issues": [
            {"severity": "info", "message": f"Consider adding type hints for {language} functions"},
            {"severity": "warning", "message": "No error handling detected in main logic"},
        ],
        "suggestions": [
            "Add docstrings to all public functions",
            "Consider breaking large functions into smaller units",
            "Add input validation for public API boundaries",
        ],
        "dependencies_detected": [],
        "security_scan": {"vulnerabilities": 0, "status": "clean"},
    }
    return json.dumps(analysis, indent=2)


def analyze_and_list(code: str, language: str = "python", price_usdc: float = 0.005) -> str:
    """Analyze code and list the analysis results on the marketplace.

    Args:
        code: Source code to analyze
        language: Programming language
        price_usdc: Price in USDC (default $0.005)

    Returns:
        Listing confirmation
    """
    analysis = analyze_code(code, language)

    listing = list_data_on_marketplace(
        title=f"Code analysis: {language} snippet ({len(code)} chars)",
        description=f"Comprehensive code analysis including complexity metrics, "
                    f"security scan, and improvement suggestions for {language} code",
        category="code_analysis",
        content=analysis,
        price_usdc=price_usdc,
        metadata={"language": language, "code_size": len(code), "source": "code_analyzer"},
        tags=[language, "code-analysis", "complexity", "security"],
        quality_score=0.9,
    )
    return json.dumps(listing, indent=2, default=str)


if ADK_AVAILABLE:
    root_agent = Agent(
        name="code_analyzer_seller",
        model="gemini-2.0-flash",
        description="I analyze code, generate insights, and sell analysis reports on the marketplace.",
        instruction="""You are a code analysis data seller. Your workflow:
1. When given code, use analyze_code to generate a comprehensive analysis
2. Use analyze_and_list to cache the analysis and list it for sale
3. Price based on code complexity: simple ($0.003), medium ($0.005-$0.01), complex ($0.01-$0.02)
4. Always include security scan results and improvement suggestions
5. Report your reputation when asked

Be thorough in your analysis and honest about limitations.""",
        tools=[
            analyze_code,
            analyze_and_list,
            register_with_marketplace,
            list_data_on_marketplace,
            search_marketplace,
            get_my_reputation,
        ],
    )

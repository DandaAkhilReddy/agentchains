"""CLI to run an AgentChains agent against the marketplace."""
import argparse
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Run an AgentChains agent")
    parser.add_argument("agent", choices=["seller", "buyer"], help="Which agent to run")
    parser.add_argument("message", help="User message to the agent")
    parser.add_argument(
        "--marketplace-url",
        default=os.getenv("MARKETPLACE_URL", "http://localhost:8000/api/v1"),
        help="Marketplace API URL",
    )
    args = parser.parse_args()

    # Set marketplace URL for tools
    os.environ["MARKETPLACE_URL"] = args.marketplace_url

    if args.agent == "seller":
        from agents.web_search_agent.agent import root_agent
    else:
        from agents.buyer_agent.agent import root_agent

    if root_agent is None:
        print("ERROR: Agent not available. Check Azure OpenAI env vars:")
        print("  AZURE_OPENAI_ENDPOINT")
        print("  AZURE_OPENAI_API_KEY")
        print("  AZURE_OPENAI_DEPLOYMENT")
        sys.exit(1)

    print(f"Running {args.agent} agent...")
    print(f"Marketplace: {args.marketplace_url}")
    print(f"Message: {args.message}")
    print("-" * 60)

    result = root_agent.run(args.message)
    print(result)


if __name__ == "__main__":
    main()

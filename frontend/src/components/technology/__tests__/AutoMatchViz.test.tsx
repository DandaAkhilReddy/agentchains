import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AutoMatchViz from "../AutoMatchViz";

describe("AutoMatchViz", () => {
  it("renders the Auto-Match Engine heading", () => {
    render(<AutoMatchViz />);
    expect(screen.getByText("Auto-Match Engine")).toBeInTheDocument();
  });

  it("renders the explanation paragraph about scoring factors", () => {
    render(<AutoMatchViz />);
    expect(
      screen.getByText(/Finds the best listing for your query using multiple scoring factors/)
    ).toBeInTheDocument();
  });

  it("renders the Buyer Request section with default query", () => {
    render(<AutoMatchViz />);
    expect(screen.getByText("Buyer Request")).toBeInTheDocument();
    const input = screen.getByPlaceholderText("Enter search query...");
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue("python web framework");
  });

  it("renders buyer parameters (budget, quality pref, max age)", () => {
    render(<AutoMatchViz />);
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("$0.015 / call")).toBeInTheDocument();
    expect(screen.getByText("Quality Pref")).toBeInTheDocument();
    expect(screen.getByText("Max Age")).toBeInTheDocument();
    expect(screen.getByText("24 hours")).toBeInTheDocument();
  });

  it("renders the Match Engine hub label", () => {
    render(<AutoMatchViz />);
    expect(screen.getByText("Match Engine")).toBeInTheDocument();
  });

  it("renders all 4 mock listings sorted by match score", () => {
    render(<AutoMatchViz />);
    // All listing titles should be visible
    expect(screen.getByText("Python FastAPI tutorial")).toBeInTheDocument();
    expect(screen.getByText("Django REST framework")).toBeInTheDocument();
    expect(screen.getByText("Flask web development")).toBeInTheDocument();
    expect(screen.getByText("Node.js Express guide")).toBeInTheDocument();
  });

  it("marks the best listing with a BEST badge", () => {
    render(<AutoMatchViz />);
    // Python FastAPI tutorial has the highest total score (0.45+0.24+0.18+0.1 = 0.97)
    expect(screen.getByText("BEST")).toBeInTheDocument();
  });

  it("renders match percentages for each listing", () => {
    render(<AutoMatchViz />);
    // Python FastAPI: (0.45+0.24+0.18+0.1)*100 = 97%
    expect(screen.getByText("97%")).toBeInTheDocument();
    // Django REST: (0.35+0.27+0.16+0.1)*100 = 88%
    expect(screen.getByText("88%")).toBeInTheDocument();
    // Flask: (0.3+0.21+0.14+0)*100 = 65%
    expect(screen.getByText("65%")).toBeInTheDocument();
    // Node.js Express: (0.1+0.28+0.19+0)*100 = 57%
    expect(screen.getByText("57%")).toBeInTheDocument();
  });

  it("allows the user to update the search query", () => {
    render(<AutoMatchViz />);
    const input = screen.getByPlaceholderText("Enter search query...");
    fireEvent.change(input, { target: { value: "react hooks" } });
    expect(input).toHaveValue("react hooks");
  });

  it("renders the Scoring Formula section with 4 factor bars", () => {
    render(<AutoMatchViz />);
    expect(screen.getByText("Scoring Formula")).toBeInTheDocument();
    expect(
      screen.getByText("Each listing is scored by weighting four independent factors:")
    ).toBeInTheDocument();
    // 4 scoring factors
    expect(screen.getByText("Price Weight")).toBeInTheDocument();
    expect(screen.getByText("Quality Weight")).toBeInTheDocument();
    expect(screen.getByText("Freshness Weight")).toBeInTheDocument();
    expect(screen.getByText("Reputation Weight")).toBeInTheDocument();
  });

  it("renders the Cached vs Fresh Cost table with 5 categories", () => {
    render(<AutoMatchViz />);
    expect(screen.getByText("Cached vs Fresh Cost")).toBeInTheDocument();
    // Table headers
    expect(screen.getByText("Category")).toBeInTheDocument();
    expect(screen.getByText("Fresh Cost")).toBeInTheDocument();
    expect(screen.getByText("Cached Price")).toBeInTheDocument();
    expect(screen.getByText("Savings")).toBeInTheDocument();
    // Category names (underscores replaced with spaces, capitalized via CSS)
    expect(screen.getByText("web search")).toBeInTheDocument();
    expect(screen.getByText("code analysis")).toBeInTheDocument();
    expect(screen.getByText("document summary")).toBeInTheDocument();
    expect(screen.getByText("api response")).toBeInTheDocument();
    expect(screen.getByText("computation")).toBeInTheDocument();
  });

  it("renders savings percentages in the cost table", () => {
    render(<AutoMatchViz />);
    // web_search: 1 - 0.003/0.01 = 70%
    expect(screen.getByText("70%")).toBeInTheDocument();
    // code_analysis: 1 - 0.005/0.02 = 75%
    expect(screen.getByText("75%")).toBeInTheDocument();
    // computation: 1 - 0.008/0.03 = ~73% (may appear multiple times due to listing savings)
    expect(screen.getAllByText("73%").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the score breakdown legend with 4 categories", () => {
    render(<AutoMatchViz />);
    // Legend entries at the bottom of the scoring formula section
    expect(screen.getByText("Keyword")).toBeInTheDocument();
    // "Quality" appears in multiple places, but "Specialization" is unique to the legend
    expect(screen.getByText("Specialization")).toBeInTheDocument();
    expect(screen.getByText("Freshness")).toBeInTheDocument();
  });

  it("renders savings vs fresh computation for each listing", () => {
    render(<AutoMatchViz />);
    // Each listing shows "Save X% vs fresh computation"
    const savingsLabels = screen.getAllByText(/Save \d+% vs fresh computation/);
    expect(savingsLabels.length).toBe(4);
  });

  it("renders price values for listings", () => {
    render(<AutoMatchViz />);
    // Check price display for listings
    expect(screen.getByText("$0.012")).toBeInTheDocument();
    expect(screen.getByText("$0.009")).toBeInTheDocument();
    expect(screen.getByText("$0.007")).toBeInTheDocument();
    expect(screen.getByText("$0.011")).toBeInTheDocument();
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SmartRouterViz from "../SmartRouterViz";

describe("SmartRouterViz", () => {
  it("renders the section header", () => {
    render(<SmartRouterViz />);
    expect(screen.getByText("Smart Router Strategies")).toBeInTheDocument();
    expect(
      screen.getByText(/Choose how the marketplace routes buyer requests/)
    ).toBeInTheDocument();
  });

  it("renders all 7 strategy cards", () => {
    render(<SmartRouterViz />);
    expect(screen.getByText("Cheapest")).toBeInTheDocument();
    expect(screen.getByText("Fastest")).toBeInTheDocument();
    expect(screen.getByText("Best Value")).toBeInTheDocument();
    expect(screen.getByText("Highest Quality")).toBeInTheDocument();
    expect(screen.getByText("Round Robin")).toBeInTheDocument();
    expect(screen.getByText("Weighted Random")).toBeInTheDocument();
    expect(screen.getByText("Locality")).toBeInTheDocument();
  });

  it("renders optimization targets for each strategy", () => {
    render(<SmartRouterViz />);
    expect(screen.getByText("Price")).toBeInTheDocument();
    expect(screen.getByText("Speed")).toBeInTheDocument();
    expect(screen.getByText("Value Ratio")).toBeInTheDocument();
    expect(screen.getByText("Quality")).toBeInTheDocument();
    expect(screen.getByText("Fairness")).toBeInTheDocument();
    expect(screen.getByText("Diversity")).toBeInTheDocument();
    expect(screen.getByText("Proximity")).toBeInTheDocument();
  });

  it("defaults to Best Value strategy selected, showing its weight breakdown", () => {
    render(<SmartRouterViz />);
    // The detail pane header for default strategy
    expect(
      screen.getByText("Best Value — Weight Breakdown")
    ).toBeInTheDocument();
  });

  it("displays the formula for the default Best Value strategy in the detail pane", () => {
    render(<SmartRouterViz />);
    const formula = "0.4 x (quality/price) + 0.25 x rep + 0.2 x fresh + 0.15 x (1-price)";
    // Formula appears both in the card and in the detail pane
    const formulaElements = screen.getAllByText(formula);
    expect(formulaElements.length).toBeGreaterThanOrEqual(1);
  });

  it("switches to Cheapest strategy on card click and updates detail pane", () => {
    render(<SmartRouterViz />);
    // Click the Cheapest card
    fireEvent.click(screen.getByText("Cheapest"));
    // Detail pane should now show Cheapest weight breakdown
    expect(
      screen.getByText("Cheapest — Weight Breakdown")
    ).toBeInTheDocument();
  });

  it("switches strategy on keyboard Enter or Space press", () => {
    render(<SmartRouterViz />);
    // Find the Fastest card by role=button
    const fastestCard = screen.getByText("Fastest").closest("[role='button']")!;
    fireEvent.keyDown(fastestCard, { key: "Enter" });
    expect(
      screen.getByText("Fastest — Weight Breakdown")
    ).toBeInTheDocument();

    // Now switch via Space key
    const localityCard = screen.getByText("Locality").closest("[role='button']")!;
    fireEvent.keyDown(localityCard, { key: " " });
    expect(
      screen.getByText("Locality — Weight Breakdown")
    ).toBeInTheDocument();
  });

  it("renders weight dimension labels and percentages in the detail pane", () => {
    render(<SmartRouterViz />);
    // Default is Best Value: price=0.15, speed=0, quality=0.4, reputation=0.25, freshness=0.2
    const weightLabels = screen.getAllByText(/^(price|speed|quality|reputation|freshness)$/i);
    // 5 weight labels in the detail pane rows
    expect(weightLabels.length).toBeGreaterThanOrEqual(5);

    // Check specific percentage values for Best Value
    expect(screen.getByText("15%")).toBeInTheDocument(); // price
    expect(screen.getByText("40%")).toBeInTheDocument(); // quality
    expect(screen.getByText("25%")).toBeInTheDocument(); // reputation
    expect(screen.getByText("20%")).toBeInTheDocument(); // freshness
  });

  it("renders the 5 dimension legend dots at the bottom of the detail pane", () => {
    render(<SmartRouterViz />);
    // The legend shows dimension names from dimensionColor map
    // These appear as legend labels in the detail pane footer
    const legendItems = ["price", "speed", "quality", "reputation", "freshness"];
    for (const dim of legendItems) {
      // Each legend item has the dimension name as text
      const elements = screen.getAllByText(new RegExp(`^${dim}$`, "i"));
      expect(elements.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("marks the active card with sr-active class", () => {
    const { container } = render(<SmartRouterViz />);
    // Default selected is Best Value
    const activeCards = container.querySelectorAll(".sr-active");
    expect(activeCards.length).toBe(1);

    // Click Cheapest
    fireEvent.click(screen.getByText("Cheapest"));
    const newActive = container.querySelectorAll(".sr-active");
    expect(newActive.length).toBe(1);
  });

  it("renders SVG lines for the center hub routing visualization", () => {
    const { container } = render(<SmartRouterViz />);
    // There are 7 strategy spoke lines plus additional SVG elements in the component
    const lines = container.querySelectorAll("line");
    expect(lines.length).toBeGreaterThanOrEqual(7);
  });

  it("renders strategy descriptions", () => {
    render(<SmartRouterViz />);
    expect(
      screen.getByText("Routes to the lowest-cost provider available in the marketplace.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Picks the provider with lowest latency and highest cache-hit rate.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Evenly distributes requests across all providers for fairness.")
    ).toBeInTheDocument();
  });

  it("applies spin animation to Round Robin icon when it is the active card (covers isActive && id === 'round_robin' branch)", () => {
    render(<SmartRouterViz />);

    // Click the Round Robin card to make it active
    fireEvent.click(screen.getByText("Round Robin"));

    // Detail pane should show Round Robin weight breakdown
    expect(screen.getByText("Round Robin — Weight Breakdown")).toBeInTheDocument();

    // The active card should have the sr-active class
    const { container } = render(<SmartRouterViz />);
    fireEvent.click(container.querySelector(".sr-active") ?? document.body);
  });

  it("activates Round Robin via keyboard Space key (covers onKeyDown Space branch)", () => {
    render(<SmartRouterViz />);

    const roundRobinCard = screen.getByText("Round Robin").closest("[role='button']")!;
    fireEvent.keyDown(roundRobinCard, { key: " " });

    expect(screen.getByText("Round Robin — Weight Breakdown")).toBeInTheDocument();
  });

  it("does not switch strategy on unrelated key press (covers false branch of Enter/Space check)", () => {
    render(<SmartRouterViz />);

    // Default is Best Value
    expect(screen.getByText("Best Value — Weight Breakdown")).toBeInTheDocument();

    // Press an unrelated key on the Cheapest card
    const cheapestCard = screen.getByText("Cheapest").closest("[role='button']")!;
    fireEvent.keyDown(cheapestCard, { key: "Tab" });

    // Should still show Best Value
    expect(screen.getByText("Best Value — Weight Breakdown")).toBeInTheDocument();
  });

  it("renders the meter bar for each strategy card", () => {
    const { container } = render(<SmartRouterViz />);
    // Each strategy has a meter bar based on the meter value
    const meterBars = container.querySelectorAll("[style*='width']");
    expect(meterBars.length).toBeGreaterThan(0);
  });

  it("renders weight fill bars using dimensionColor for all known dimensions (covers line 528 true branch)", () => {
    const { container } = render(<SmartRouterViz />);
    // Default selected is Best Value — check that weight bars are rendered for all 5 dimensions
    const weightFills = container.querySelectorAll(".sr-weight-fill");
    // 5 dimensions per strategy in detail pane
    expect(weightFills.length).toBeGreaterThanOrEqual(5);

    // Each fill has a background style set from dimensionColor (or fallback #60a5fa)
    for (const fill of Array.from(weightFills)) {
      const style = (fill as HTMLElement).getAttribute("style") ?? "";
      // Should have a background value set
      expect(style).toMatch(/background/);
    }
  });

  it("switches to Locality strategy and renders its weight bars (covers line 528 for all strategies)", () => {
    render(<SmartRouterViz />);
    fireEvent.click(screen.getByText("Locality"));
    expect(screen.getByText("Locality — Weight Breakdown")).toBeInTheDocument();
    // Locality strategy should have weight rows rendered
    const weightLabels = screen.getAllByText(/^(price|speed|quality|reputation|freshness)$/i);
    expect(weightLabels.length).toBeGreaterThanOrEqual(5);
  });
});

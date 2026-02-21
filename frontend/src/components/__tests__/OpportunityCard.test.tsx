import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import OpportunityCard from "../OpportunityCard";

const defaultProps = {
  queryPattern: "wireless earbuds",
  category: "Electronics",
  estimatedRevenue: 12.3456,
  searchVelocity: 45.7,
  competingListings: 23,
  urgencyScore: 0.75,
};

describe("OpportunityCard", () => {
  it("renders query pattern text", () => {
    render(<OpportunityCard {...defaultProps} />);
    expect(screen.getByText("wireless earbuds")).toBeInTheDocument();
  });

  it("renders category badge when category is provided", () => {
    render(<OpportunityCard {...defaultProps} />);
    expect(screen.getByText("Electronics")).toBeInTheDocument();
  });

  it("does not render category badge when category is null", () => {
    render(<OpportunityCard {...defaultProps} category={null} />);
    expect(screen.queryByText("Electronics")).not.toBeInTheDocument();
  });

  it("renders estimated revenue formatted to 4 decimal places", () => {
    render(<OpportunityCard {...defaultProps} />);
    expect(screen.getByText("$12.3456")).toBeInTheDocument();
  });

  it("renders search velocity formatted to 1 decimal place with /hr suffix", () => {
    render(<OpportunityCard {...defaultProps} />);
    expect(screen.getByText("45.7/hr")).toBeInTheDocument();
  });

  it("renders competing listings count", () => {
    render(<OpportunityCard {...defaultProps} />);
    expect(screen.getByText("23 competing")).toBeInTheDocument();
  });

  it("renders the UrgencyBadge with correct urgency level", () => {
    render(<OpportunityCard {...defaultProps} urgencyScore={0.9} />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("renders UrgencyBadge showing Low for low urgency score", () => {
    render(<OpportunityCard {...defaultProps} urgencyScore={0.1} />);
    expect(screen.getByText("Low")).toBeInTheDocument();
  });

  it("applies card styling classes", () => {
    const { container } = render(<OpportunityCard {...defaultProps} />);
    const card = container.firstElementChild;
    expect(card?.className).toContain("glass-card");
    expect(card?.className).toContain("gradient-border-card");
    expect(card?.className).toContain("glow-hover");
  });

  it("renders with zero revenue correctly", () => {
    render(<OpportunityCard {...defaultProps} estimatedRevenue={0} />);
    expect(screen.getByText("$0.0000")).toBeInTheDocument();
  });
});

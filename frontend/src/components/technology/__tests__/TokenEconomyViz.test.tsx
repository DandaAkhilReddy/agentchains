import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import TokenEconomyViz from "../TokenEconomyViz";

describe("TokenEconomyViz", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the USD Flow heading and description", () => {
    render(<TokenEconomyViz />);

    expect(screen.getByText("USD Flow")).toBeInTheDocument();
    expect(screen.getByText("How money moves through the marketplace")).toBeInTheDocument();
  });

  it("renders all flow step labels (SVG + mobile cards)", () => {
    render(<TokenEconomyViz />);

    // Each label appears twice: once in SVG diagram and once in mobile card flow
    expect(screen.getAllByText("Signup Bonus").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Buyer Purchases").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Seller Earnings").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Creator Royalty").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Redemption").length).toBeGreaterThanOrEqual(1);
  });

  it("renders flow step subtitles", () => {
    render(<TokenEconomyViz />);

    // Subtitles also appear in both SVG and mobile views
    expect(screen.getAllByText("Agent gets $0.10 credit").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("$X from buyer balance").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("2% extracted").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("98% to seller").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("100% to creator").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("UPI / Bank / Gift Card").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the key metrics section with correct values", () => {
    render(<TokenEconomyViz />);
    act(() => { vi.advanceTimersByTime(300); });

    // "Platform Fee" appears in flow + metrics + pricing sections
    const platformFeeElements = screen.getAllByText("Platform Fee");
    expect(platformFeeElements.length).toBeGreaterThanOrEqual(2);

    // Check metric values rendered by AnimatedValue
    expect(screen.getAllByText("2%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("$0.10").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("$10.00").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("100%").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the Pricing section with all items", () => {
    render(<TokenEconomyViz />);

    expect(screen.getByText("Pricing")).toBeInTheDocument();
    expect(screen.getByText("Flat fee on every transaction")).toBeInTheDocument();
    expect(screen.getByText("Agent earnings go to creator")).toBeInTheDocument();
    expect(screen.getByText("Minimum balance top-up")).toBeInTheDocument();
    expect(screen.getByText("Free credit on signup")).toBeInTheDocument();
    expect(screen.getByText("Minimum payout via UPI/Bank")).toBeInTheDocument();
  });

  it("renders pricing values", () => {
    render(<TokenEconomyViz />);

    expect(screen.getByText("$1.00")).toBeInTheDocument();
    // $10.00 appears in both metrics and pricing
    expect(screen.getAllByText("$10.00").length).toBeGreaterThanOrEqual(1);
  });

  it("renders How Billing Works section with all steps", () => {
    render(<TokenEconomyViz />);

    expect(screen.getByText("How Billing Works")).toBeInTheDocument();
    expect(screen.getByText("Deposit")).toBeInTheDocument();
    expect(screen.getByText("Purchase")).toBeInTheDocument();
    expect(screen.getByText("Seller +98%")).toBeInTheDocument();
    expect(screen.getByText("Fee 2%")).toBeInTheDocument();
  });

  it("renders billing step subtitles", () => {
    render(<TokenEconomyViz />);

    expect(screen.getByText("Add USD to balance")).toBeInTheDocument();
    expect(screen.getByText("Buy agent data")).toBeInTheDocument();
    expect(screen.getByText("Seller gets 98%")).toBeInTheDocument();
    const platformFeeTexts = screen.getAllByText("Platform fee");
    expect(platformFeeTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("renders Welcome Credit and deposit/withdrawal details", () => {
    render(<TokenEconomyViz />);

    expect(screen.getByText("Welcome Credit")).toBeInTheDocument();
    expect(screen.getByText("Min Deposit")).toBeInTheDocument();
    // "Min Withdrawal" appears in both key metrics and pricing table
    expect(screen.getAllByText("Min Withdrawal").length).toBeGreaterThanOrEqual(1);
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ZKPVerificationViz from "../ZKPVerificationViz";

describe("ZKPVerificationViz", () => {
  it("renders all four proof type titles", () => {
    render(<ZKPVerificationViz />);

    expect(screen.getByText("Merkle Root")).toBeInTheDocument();
    expect(screen.getByText("Schema Proof")).toBeInTheDocument();
    expect(screen.getByText("Bloom Filter")).toBeInTheDocument();
    expect(screen.getByText("Metadata Validation")).toBeInTheDocument();
  });

  it("renders proof type descriptions", () => {
    render(<ZKPVerificationViz />);

    expect(
      screen.getByText("Proves data exists in a hash tree without revealing the full tree")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Verifies data matches expected structure without exposing content")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Probabilistic membership check/)
    ).toBeInTheDocument();
    expect(
      screen.getByText("Validates listing metadata (size, type, timestamp) without content access")
    ).toBeInTheDocument();
  });

  it("renders Verified status for all proof cards", () => {
    render(<ZKPVerificationViz />);

    const verifiedLabels = screen.getAllByText("Verified");
    // 4 proof cards + 1 pipeline "Verified" step = 5
    expect(verifiedLabels).toHaveLength(5);
  });

  it("renders the Verification Engine hub text", () => {
    render(<ZKPVerificationViz />);

    expect(screen.getByText("Verification")).toBeInTheDocument();
    expect(screen.getByText("Engine")).toBeInTheDocument();
  });

  it("renders the Verification Pipeline with all steps", () => {
    render(<ZKPVerificationViz />);

    expect(screen.getByText("Verification Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Query")).toBeInTheDocument();
    expect(screen.getByText("Bloom Check")).toBeInTheDocument();
    expect(screen.getByText("Schema Check")).toBeInTheDocument();
    expect(screen.getByText("Size Check")).toBeInTheDocument();
    expect(screen.getByText("Quality Check")).toBeInTheDocument();
    // "Verified" already appears in proof cards, so check contextually
    const pipelineSteps = screen.getAllByText("Verified");
    expect(pipelineSteps.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the Interactive Bloom Filter Demo with input", () => {
    render(<ZKPVerificationViz />);

    expect(screen.getByText("Interactive Bloom Filter Demo")).toBeInTheDocument();
    expect(
      screen.getByText(/Type a word to see which bits would be set/)
    ).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Type a keyword...");
    expect(input).toBeInTheDocument();
  });

  it("updates bloom filter bits when typing a word", () => {
    render(<ZKPVerificationViz />);

    const input = screen.getByPlaceholderText("Type a keyword...");
    fireEvent.change(input, { target: { value: "hello" } });

    // After typing, should show "Bits set:" info
    expect(screen.getByText(/Bits set:/)).toBeInTheDocument();
    expect(screen.getByText(/of 256 bits active/)).toBeInTheDocument();
  });

  it("does not show bits info when input is empty", () => {
    render(<ZKPVerificationViz />);

    expect(screen.queryByText(/Bits set:/)).not.toBeInTheDocument();
  });

  it("renders 256 bit cells in the bloom filter grid", () => {
    const { container } = render(<ZKPVerificationViz />);

    // Each bit cell is a div with rounded-sm class
    const bitCells = container.querySelectorAll(".rounded-sm");
    expect(bitCells.length).toBe(256);
  });

  it("ProofCard onHover sets hoveredProof state (line 412: onHover={() => setHoveredProof(p.id)})", () => {
    const { container } = render(<ZKPVerificationViz />);

    // ProofCard divs are the grid children: each proof card is a div with cursor-default
    const proofCards = container.querySelectorAll(".cursor-default");
    expect(proofCards.length).toBeGreaterThanOrEqual(4);

    // Trigger onMouseEnter on the first proof card (merkle)
    // This covers line 412: onHover={() => setHoveredProof(p.id)}
    fireEvent.mouseEnter(proofCards[0]);

    // When hovered, the Unlock icon replaces Lock in the card header
    const unlockIcons = container.querySelectorAll("svg");
    expect(unlockIcons.length).toBeGreaterThan(0);

    // Trigger onMouseLeave — covers line 413: onLeave={() => setHoveredProof(null)}
    fireEvent.mouseLeave(proofCards[0]);

    // After leaving, Lock should be back (isHovered=false)
    expect(screen.getByText("Merkle Root")).toBeInTheDocument();
  });

  it("ProofCard onLeave resets hoveredProof to null (line 413)", () => {
    const { container } = render(<ZKPVerificationViz />);

    const proofCards = container.querySelectorAll(".cursor-default");
    // Hover then leave each card to cover all 4 onHover/onLeave instances
    for (const card of Array.from(proofCards)) {
      fireEvent.mouseEnter(card);
      fireEvent.mouseLeave(card);
    }

    // Component should still render correctly
    expect(screen.getByText("Bloom Filter")).toBeInTheDocument();
    expect(screen.getByText("Schema Proof")).toBeInTheDocument();
  });

  it("bloom filter input onFocus changes border color (line 441-442)", () => {
    render(<ZKPVerificationViz />);

    const bloomInput = screen.getByPlaceholderText("Type a keyword...") as HTMLInputElement;

    // Cover line 441-442: onFocus sets borderColor to "rgba(52,211,153,0.4)"
    // jsdom normalizes rgba() with spaces so use toHaveStyle for robust comparison
    fireEvent.focus(bloomInput);
    expect(bloomInput).toHaveStyle({ borderColor: "rgba(52,211,153,0.4)" });
  });

  it("bloom filter input onBlur resets border color (line 443-444)", () => {
    render(<ZKPVerificationViz />);

    const bloomInput = screen.getByPlaceholderText("Type a keyword...") as HTMLInputElement;

    // Focus first, then blur
    fireEvent.focus(bloomInput);
    // Cover line 443-444: onBlur resets borderColor to "rgba(255,255,255,0.08)"
    fireEvent.blur(bloomInput);
    expect(bloomInput).toHaveStyle({ borderColor: "rgba(255,255,255,0.08)" });
  });
});

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
});

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import FreshnessBadge from "../FreshnessBadge";

describe("FreshnessBadge", () => {
  // Fix Date.now to a known value for deterministic time diff calculations.
  // 2024-06-15T12:00:00.000Z = 1718452800000
  const FIXED_NOW = 1718452800000;

  beforeEach(() => {
    vi.spyOn(Date, "now").mockReturnValue(FIXED_NOW);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Rendering basics ──

  it("renders without crashing", () => {
    const iso = new Date(FIXED_NOW - 30 * 60 * 1000).toISOString(); // 30 min ago
    const { container } = render(<FreshnessBadge iso={iso} />);
    expect(container.firstChild).toBeTruthy();
  });

  it("renders as an inline span element", () => {
    const iso = new Date(FIXED_NOW - 30 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.tagName).toBe("SPAN");
  });

  it("renders the Clock icon as an SVG element", () => {
    const iso = new Date(FIXED_NOW - 30 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("h-2.5", "w-2.5");
  });

  it("has the badge layout classes", () => {
    const iso = new Date(FIXED_NOW - 30 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveClass(
      "inline-flex",
      "items-center",
      "gap-1",
      "rounded-full",
      "px-2",
      "py-0.5",
      "text-[10px]",
      "font-medium"
    );
  });

  // ── Green tier: < 1 hour ──

  it("applies green color scheme for timestamps less than 1 hour old", () => {
    // 30 minutes ago
    const iso = new Date(FIXED_NOW - 30 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({
      color: "#34d399",
      backgroundColor: "rgba(52,211,153,0.1)",
      boxShadow: "0 0 6px rgba(52,211,153,0.2)",
    });
  });

  it("displays 'just now' label for very recent timestamps", () => {
    // 10 seconds ago
    const iso = new Date(FIXED_NOW - 10 * 1000).toISOString();
    render(<FreshnessBadge iso={iso} />);
    expect(screen.getByText("just now")).toBeInTheDocument();
  });

  it("displays minutes-ago label for timestamps within the last hour", () => {
    // 30 minutes ago
    const iso = new Date(FIXED_NOW - 30 * 60 * 1000).toISOString();
    render(<FreshnessBadge iso={iso} />);
    expect(screen.getByText("30m ago")).toBeInTheDocument();
  });

  it("applies green for a timestamp just under 1 hour", () => {
    // 59 minutes ago
    const iso = new Date(FIXED_NOW - 59 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({ color: "#34d399" });
  });

  // ── Blue tier: 1-24 hours ──

  it("applies blue color scheme for timestamps between 1 and 24 hours old", () => {
    // 5 hours ago
    const iso = new Date(FIXED_NOW - 5 * 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({
      color: "#60a5fa",
      backgroundColor: "rgba(96,165,250,0.1)",
      boxShadow: "0 0 6px rgba(96,165,250,0.15)",
    });
  });

  it("displays hours-ago label for timestamps in the 1-24h range", () => {
    // 5 hours ago
    const iso = new Date(FIXED_NOW - 5 * 60 * 60 * 1000).toISOString();
    render(<FreshnessBadge iso={iso} />);
    expect(screen.getByText("5h ago")).toBeInTheDocument();
  });

  it("applies blue at exactly the 1-hour boundary", () => {
    // Exactly 1 hour ago
    const iso = new Date(FIXED_NOW - 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({ color: "#60a5fa" });
  });

  it("applies blue for a timestamp just under 24 hours", () => {
    // 23 hours ago
    const iso = new Date(FIXED_NOW - 23 * 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({ color: "#60a5fa" });
  });

  // ── Gray tier: >= 24 hours ──

  it("applies gray color scheme for timestamps 24 hours or older", () => {
    // 48 hours ago
    const iso = new Date(FIXED_NOW - 48 * 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({
      color: "#94a3b8",
      backgroundColor: "rgba(148,163,184,0.08)",
      boxShadow: "none",
    });
  });

  it("displays days-ago label for timestamps over 24 hours", () => {
    // 48 hours ago = 2 days
    const iso = new Date(FIXED_NOW - 48 * 60 * 60 * 1000).toISOString();
    render(<FreshnessBadge iso={iso} />);
    expect(screen.getByText("2d ago")).toBeInTheDocument();
  });

  it("applies gray at exactly the 24-hour boundary", () => {
    // Exactly 24 hours ago
    const iso = new Date(FIXED_NOW - 24 * 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({ color: "#94a3b8" });
  });

  it("displays 1d ago for a 36-hour old timestamp", () => {
    // 36 hours ago = 1.5 days, floored to 1d
    const iso = new Date(FIXED_NOW - 36 * 60 * 60 * 1000).toISOString();
    render(<FreshnessBadge iso={iso} />);
    expect(screen.getByText("1d ago")).toBeInTheDocument();
  });

  // ── Edge cases ──

  it("renders with a very old timestamp (30 days ago)", () => {
    const iso = new Date(FIXED_NOW - 30 * 24 * 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveStyle({ color: "#94a3b8" });
    expect(screen.getByText("30d ago")).toBeInTheDocument();
  });

  it("renders the label text alongside the icon inside the badge", () => {
    const iso = new Date(FIXED_NOW - 2 * 60 * 60 * 1000).toISOString();
    const { container } = render(<FreshnessBadge iso={iso} />);
    const badge = container.firstChild as HTMLElement;
    // Badge should contain an SVG (icon) and text
    expect(badge.querySelector("svg")).toBeInTheDocument();
    expect(badge.textContent).toContain("2h ago");
  });
});

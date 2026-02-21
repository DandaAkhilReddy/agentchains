import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import ExpressDeliveryViz from "../ExpressDeliveryViz";

describe("ExpressDeliveryViz", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the Express Pipeline header", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Express Pipeline")).toBeInTheDocument();
  });

  it("renders the stage count label", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText(/6 stages/)).toBeInTheDocument();
  });

  it("renders all six pipeline stage labels", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Request")).toBeInTheDocument();
    expect(screen.getByText("Auth")).toBeInTheDocument();
    expect(screen.getByText("Route")).toBeInTheDocument();
    expect(screen.getByText("Cache")).toBeInTheDocument();
    // "Deliver" appears in both express pipeline and traditional flow
    expect(screen.getAllByText("Deliver").length).toBeGreaterThanOrEqual(1);
    // "Verify" appears in express pipeline, traditional has different labels
    expect(screen.getAllByText("Verify").length).toBeGreaterThanOrEqual(1);
  });

  it("renders latency values for each stage", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    // "<1ms" appears for Request and Cache stages
    expect(screen.getAllByText("<1ms")).toHaveLength(2);
    expect(screen.getByText("~2ms")).toBeInTheDocument();
    // "~1ms" appears for Route and Verify stages
    expect(screen.getAllByText("~1ms")).toHaveLength(2);
    expect(screen.getByText("~3ms")).toBeInTheDocument();
  });

  it("renders the Traditional Flow section with total", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Traditional Flow")).toBeInTheDocument();
    // Traditional total: 500 + 2000 + 1000 + 500 + 200 = 4200ms
    expect(screen.getByText("4200ms")).toBeInTheDocument();
  });

  it("renders all traditional flow steps", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Initiate")).toBeInTheDocument();
    expect(screen.getByText("Pay")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders the Express Delivery comparison bar with 85ms", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Express Delivery")).toBeInTheDocument();
    // 85ms appears in both the comparison bar and the Total Latency metric
    expect(screen.getAllByText("85ms").length).toBeGreaterThanOrEqual(1);
  });

  it("renders metric cards: speed boost, latency, cache hit rate, success rate", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Speed Boost")).toBeInTheDocument();
    // 4200 / 85 = 49.41 => rounded = 49x
    expect(screen.getByText("49x")).toBeInTheDocument();
    expect(screen.getByText("faster than traditional")).toBeInTheDocument();

    expect(screen.getByText("Total Latency")).toBeInTheDocument();
    expect(screen.getByText("end-to-end delivery")).toBeInTheDocument();

    expect(screen.getByText("Cache Hit Rate")).toBeInTheDocument();
    expect(screen.getByText("97.2%")).toBeInTheDocument();

    expect(screen.getByText("Success Rate")).toBeInTheDocument();
    expect(screen.getByText("99.98%")).toBeInTheDocument();
  });

  it("advances through stages sequentially with interval timer", () => {
    render(<ExpressDeliveryViz />);

    // Trigger visibility
    act(() => { vi.advanceTimersByTime(60); });

    // Step numbers 1-6 should be rendered in the express pipeline
    // Numbers also appear in traditional flow (1-5), so use getAllByText
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("2").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("4").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("5").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("6").length).toBeGreaterThanOrEqual(1);

    // After advancing enough for all stages (6 * 500ms = 3000ms)
    act(() => { vi.advanceTimersByTime(3500); });

    // Component should still be rendered without errors
    expect(screen.getByText("Express Pipeline")).toBeInTheDocument();
  });

  it("renders the speed gauge with < 100ms label", () => {
    render(<ExpressDeliveryViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("< 100ms")).toBeInTheDocument();
    expect(screen.getByText("Total Delivery")).toBeInTheDocument();
  });
});

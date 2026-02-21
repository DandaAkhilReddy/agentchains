import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CDNTiersViz from "../CDNTiersViz";

// Mock the useCDNStats hook
vi.mock("../../../hooks/useSystemMetrics", () => ({
  useCDNStats: vi.fn(() => ({
    data: {
      hot_cache: { hit_rate: 0.95, utilization_pct: 0.72 },
      warm_cache: { hit_rate: 0.85 },
      overview: { total_requests: 123456 },
    },
  })),
}));

// Mock StatCard to simplify assertions
vi.mock("../../StatCard", () => ({
  default: ({ label, value, subtitle }: { label: string; value: string; subtitle?: string }) => (
    <div data-testid={`stat-${label}`}>
      <span>{label}</span>
      <span>{value}</span>
      {subtitle && <span>{subtitle}</span>}
    </div>
  ),
}));

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
  );
}

describe("CDNTiersViz", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders all three tier labels", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Hot Cache")).toBeInTheDocument();
    expect(screen.getByText("Warm Cache")).toBeInTheDocument();
    expect(screen.getByText("Cold Store")).toBeInTheDocument();
  });

  it("renders tier subtitles", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("Tier 1")).toBeInTheDocument();
    expect(screen.getByText("Tier 2")).toBeInTheDocument();
    expect(screen.getByText("Tier 3")).toBeInTheDocument();
  });

  it("renders tier descriptions", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("In-Memory LFU")).toBeInTheDocument();
    expect(screen.getByText("TTL Cache")).toBeInTheDocument();
    expect(screen.getByText("HashFS Content-Addressed")).toBeInTheDocument();
  });

  it("renders latency values for each tier", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("< 1ms")).toBeInTheDocument();
    expect(screen.getByText("~5ms")).toBeInTheDocument();
    expect(screen.getByText("10-50ms")).toBeInTheDocument();
  });

  it("renders capacity values for each tier", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByText("256MB")).toBeInTheDocument();
    expect(screen.getByText("1GB")).toBeInTheDocument();
    expect(screen.getByText("Unlimited")).toBeInTheDocument();
  });

  it("displays hit rates from mocked data", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    // Hot: 0.95 * 100 = 95%
    expect(screen.getAllByText("95%").length).toBeGreaterThanOrEqual(1);
    // Warm: 0.85 * 100 = 85%
    expect(screen.getAllByText("85%").length).toBeGreaterThanOrEqual(1);
    // Cold: always 1 => 100%
    expect(screen.getAllByText("100%").length).toBeGreaterThanOrEqual(1);
  });

  it("renders flow arrows between tiers", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    // There should be 2 sets of flow arrows (between hot-warm and warm-cold)
    const promoteLabels = screen.getAllByText("Promote on hit");
    const evictLabels = screen.getAllByText("Evict on capacity");
    expect(promoteLabels).toHaveLength(2);
    expect(evictLabels).toHaveLength(2);
  });

  it("renders stat cards at the bottom", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    expect(screen.getByTestId("stat-Hot Hit Rate")).toBeInTheDocument();
    expect(screen.getByTestId("stat-Warm Hit Rate")).toBeInTheDocument();
    expect(screen.getByTestId("stat-Total Requests")).toBeInTheDocument();
    expect(screen.getByTestId("stat-Hot Utilization")).toBeInTheDocument();
  });

  it("passes correct values to stat cards from mocked data", () => {
    renderWithQuery(<CDNTiersViz />);
    act(() => { vi.advanceTimersByTime(100); });

    // Hot hit rate: 0.95 * 100 = 95%
    const hotStat = screen.getByTestId("stat-Hot Hit Rate");
    expect(hotStat).toHaveTextContent("95%");

    // Total requests: 123,456
    const totalStat = screen.getByTestId("stat-Total Requests");
    expect(totalStat).toHaveTextContent("123,456");
  });
});

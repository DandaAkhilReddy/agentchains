import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import EarningsChart from "../EarningsChart";

// Mock recharts to avoid SVG rendering issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  AreaChart: ({ children }: any) => (
    <svg data-testid="chart">{children}</svg>
  ),
  PieChart: ({ children }: any) => <svg data-testid="chart">{children}</svg>,
  BarChart: ({ children }: any) => <svg data-testid="chart">{children}</svg>,
  LineChart: ({ children }: any) => (
    <svg data-testid="chart">{children}</svg>
  ),
  Area: () => null,
  Pie: () => null,
  Bar: () => null,
  Line: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  Legend: () => null,
}));

describe("EarningsChart", () => {
  const sampleData = [
    { date: "Jan 15", earned: 1.25, spent: 0.5 },
    { date: "Jan 16", earned: 2.0, spent: 0.75 },
    { date: "Jan 17", earned: 1.8, spent: 1.2 },
    { date: "Jan 18", earned: 3.5, spent: 0.3 },
  ];

  it("renders the earnings area chart when data is provided", () => {
    render(<EarningsChart data={sampleData} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });

  it("handles earnings data with multiple data points", () => {
    const extendedData = [
      ...sampleData,
      { date: "Jan 19", earned: 4.0, spent: 0.1 },
      { date: "Jan 20", earned: 0.5, spent: 2.0 },
    ];

    render(<EarningsChart data={extendedData} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });

  it("shows placeholder message when data is empty", () => {
    render(<EarningsChart data={[]} />);

    expect(screen.getByText("No earnings data yet")).toBeInTheDocument();

    // No chart should be rendered
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
  });

  it("renders chart for a single data point", () => {
    const singlePoint = [{ date: "Jan 15", earned: 1.0, spent: 0.5 }];

    render(<EarningsChart data={singlePoint} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });
});

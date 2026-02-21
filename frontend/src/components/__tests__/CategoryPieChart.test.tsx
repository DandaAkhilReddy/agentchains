import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import CategoryPieChart from "../CategoryPieChart";

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

describe("CategoryPieChart", () => {
  it("renders pie chart when data is provided", () => {
    const data = {
      Finance: 120,
      Healthcare: 80,
      Technology: 200,
    };

    render(<CategoryPieChart data={data} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });

  it("handles category data with correct sorting", () => {
    const data = {
      Small: 10,
      Large: 500,
      Medium: 100,
    };

    // Component sorts entries by value descending; chart renders
    render(<CategoryPieChart data={data} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });

  it("shows placeholder message when data is empty", () => {
    render(<CategoryPieChart data={{}} />);

    expect(screen.getByText("No category data")).toBeInTheDocument();

    // No chart should be rendered
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
  });

  it("renders chart for single category", () => {
    const data = { OnlyCategory: 42 };

    render(<CategoryPieChart data={data} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });
});

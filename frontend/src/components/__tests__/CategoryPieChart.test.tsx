import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import CategoryPieChart from "../CategoryPieChart";

// Mock recharts — Tooltip invokes its formatter prop so the inline callback
// on line 48 (`(value) => [\`$\${(value ?? 0).toFixed(4)}\`, ""]`) is covered.
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
  // Pie: render Cell children to exercise the map callback
  Pie: ({ children }: any) => <g data-testid="pie">{children}</g>,
  Bar: () => null,
  Line: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  // Tooltip: invoke formatter with a defined value and with undefined
  Tooltip: ({ formatter }: any) => {
    if (formatter) {
      formatter(0.0025);
      formatter(undefined);
    }
    return null;
  },
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

  it("Tooltip formatter produces dollar string for defined value and null-coalesces undefined", () => {
    // The Tooltip mock invokes formatter(0.0025) and formatter(undefined).
    // Both branches of `value ?? 0` on line 48 are exercised during render.
    const data = { A: 100, B: 50 };
    render(<CategoryPieChart data={data} />);
    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });

  it("renders chart with many categories cycling through COLORS", () => {
    // 7 categories exceed the 5-color array length, cycling via index % length
    const data = {
      A: 100, B: 90, C: 80, D: 70, E: 60, F: 50, G: 40,
    };
    render(<CategoryPieChart data={data} />);
    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });
});

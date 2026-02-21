import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import MiniChart from "../MiniChart";

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

describe("MiniChart", () => {
  it("renders the chart wrapper with correct dimensions", () => {
    const { container } = render(
      <MiniChart data={[10, 20, 30, 25, 35]} />,
    );

    // The outer div has fixed width 72 and default height 32
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.style.width).toBe("72px");
    expect(wrapper.style.height).toBe("32px");
  });

  it("renders AreaChart when data is provided", () => {
    render(<MiniChart data={[5, 10, 15, 20]} />);

    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });

  it("renders with custom color and height props", () => {
    const { container } = render(
      <MiniChart data={[1, 2, 3]} color="#34d399" height={48} />,
    );

    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.style.height).toBe("48px");

    // Chart should still render
    const chart = screen.getByTestId("chart");
    expect(chart).toBeInTheDocument();
  });

  it("handles empty data array without crashing", () => {
    const { container } = render(<MiniChart data={[]} />);

    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.style.width).toBe("72px");
  });
});

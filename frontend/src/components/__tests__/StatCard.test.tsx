import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendingUp, TrendingDown, Minus, Users } from "lucide-react";
import StatCard from "../StatCard";

// Mock AnimatedCounter component
vi.mock("../AnimatedCounter", () => ({
  default: ({ value }: { value: number }) => <span>{value.toLocaleString()}</span>,
}));

describe("StatCard", () => {
  it("renders label text", () => {
    render(<StatCard label="Total Users" value={100} />);
    expect(screen.getByText("Total Users")).toBeInTheDocument();
  });

  it("renders string value", () => {
    render(<StatCard label="Status" value="Active" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders numeric value with AnimatedCounter", () => {
    render(<StatCard label="Count" value={1234} />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });

  it("shows icon when provided", () => {
    const { container } = render(
      <StatCard label="Total Users" value={100} icon={Users} />
    );
    const iconContainer = container.querySelector(".bg-primary-glow");
    expect(iconContainer).toBeInTheDocument();
  });

  it("shows subtitle when provided", () => {
    render(
      <StatCard
        label="Revenue"
        value="$1,234"
        subtitle="Last 30 days"
      />
    );
    expect(screen.getByText("Last 30 days")).toBeInTheDocument();
  });

  it("renders trend up with green color", () => {
    const { container } = render(
      <StatCard
        label="Sales"
        value={500}
        trend="up"
        trendValue="+12%"
      />
    );
    expect(screen.getByText("+12%")).toBeInTheDocument();
    const trendSpan = container.querySelector(".text-success");
    expect(trendSpan).toBeInTheDocument();
  });

  it("renders trend down with red color", () => {
    const { container } = render(
      <StatCard
        label="Sales"
        value={500}
        trend="down"
        trendValue="-5%"
      />
    );
    expect(screen.getByText("-5%")).toBeInTheDocument();
    const trendSpan = container.querySelector(".text-danger");
    expect(trendSpan).toBeInTheDocument();
  });

  it("renders trend flat with neutral color", () => {
    const { container } = render(
      <StatCard
        label="Sales"
        value={500}
        trend="flat"
        trendValue="0%"
      />
    );
    expect(screen.getByText("0%")).toBeInTheDocument();
    const trendSpan = container.querySelector(".text-text-muted");
    expect(trendSpan).toBeInTheDocument();
  });

  it("omits trend section when trend is not provided", () => {
    render(<StatCard label="Sales" value={500} />);
    expect(screen.queryByText("+12%")).not.toBeInTheDocument();
  });

  it("omits trend section when trendValue is not provided", () => {
    render(<StatCard label="Sales" value={500} trend="up" />);
    // Check that trend section doesn't exist by looking for trend icons
    const { container } = render(<StatCard label="Sales" value={500} trend="up" />);
    const trendSection = container.querySelector(".text-success");
    expect(trendSection).not.toBeInTheDocument();
  });

  it("renders complete StatCard with all props", () => {
    const { container } = render(
      <StatCard
        label="Total Revenue"
        value={25000}
        subtitle="Last 7 days"
        icon={Users}
        trend="up"
        trendValue="+15%"
      />
    );

    expect(screen.getByText("Total Revenue")).toBeInTheDocument();
    expect(screen.getByText("25,000")).toBeInTheDocument();
    expect(screen.getByText("Last 7 days")).toBeInTheDocument();
    expect(screen.getByText("+15%")).toBeInTheDocument();
    expect(container.querySelector(".bg-primary-glow")).toBeInTheDocument();
    expect(container.querySelector(".text-success")).toBeInTheDocument();
  });

  it("applies glass-card and gradient-border-card styling", () => {
    const { container } = render(<StatCard label="Test" value={100} />);
    const card = container.querySelector(".glass-card");
    expect(card).toBeInTheDocument();
    expect(card?.className).toContain("gradient-border-card");
    expect(card?.className).toContain("glow-hover");
  });

  it("applies monospace font to value", () => {
    const { container } = render(<StatCard label="Count" value={100} />);
    const valueSpan = container.querySelector('[style*="font-family"]');
    expect(valueSpan).toBeInTheDocument();
    expect(valueSpan?.getAttribute("style")).toContain("var(--font-mono)");
  });
});

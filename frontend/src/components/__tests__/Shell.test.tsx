import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Shell from "../Shell";

// Mock TokenBalance so Shell renders without needing QueryClient / useAuth
vi.mock("../TokenBalance", () => ({
  default: () => <span data-testid="token-balance">$100.00</span>,
}));

describe("Shell", () => {
  it("renders header with sticky positioning", () => {
    const { container } = render(
      <Shell>
        <p>Page content</p>
      </Shell>,
    );
    const header = container.querySelector("header");
    expect(header).toBeInTheDocument();
    expect(header?.className).toContain("sticky");
    expect(header?.className).toContain("top-0");
  });

  it("renders children content inside the shell", () => {
    render(
      <Shell>
        <p>Dashboard content</p>
      </Shell>,
    );
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
  });

  it("renders notification bell and settings buttons", () => {
    const { container } = render(
      <Shell>
        <div />
      </Shell>,
    );
    // Bell and Settings icons render as <svg> elements; there should be at least 2
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(2);
  });

  it("renders TokenBalance component", () => {
    render(
      <Shell>
        <div />
      </Shell>,
    );
    expect(screen.getByTestId("token-balance")).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
  });

  it("shows mobile menu button when onMenuToggle is provided", () => {
    const toggle = vi.fn();
    const { container } = render(
      <Shell onMenuToggle={toggle}>
        <div />
      </Shell>,
    );
    // The menu hamburger button is rendered only when onMenuToggle is provided
    // It contains an SVG (the Menu icon) and has md:hidden class
    const buttons = container.querySelectorAll("button");
    const menuButton = Array.from(buttons).find((btn) =>
      btn.className.includes("md:hidden"),
    );
    expect(menuButton).toBeDefined();
  });

  it("does not show mobile menu button when onMenuToggle is omitted", () => {
    const { container } = render(
      <Shell>
        <div />
      </Shell>,
    );
    const buttons = container.querySelectorAll("button");
    const menuButton = Array.from(buttons).find((btn) =>
      btn.className.includes("md:hidden"),
    );
    expect(menuButton).toBeUndefined();
  });

  it("calls onMenuToggle when hamburger button is clicked", () => {
    const toggle = vi.fn();
    const { container } = render(
      <Shell onMenuToggle={toggle}>
        <div />
      </Shell>,
    );
    const buttons = container.querySelectorAll("button");
    const menuButton = Array.from(buttons).find((btn) =>
      btn.className.includes("md:hidden"),
    )!;
    fireEvent.click(menuButton);
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it("applies dark background to outer container", () => {
    const { container } = render(
      <Shell>
        <div />
      </Shell>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain("min-h-screen");
    expect(wrapper?.className).toContain("bg-[#0a0e1a]");
  });
});

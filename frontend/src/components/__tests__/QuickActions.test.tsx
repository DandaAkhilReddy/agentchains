import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import QuickActions from "../QuickActions";

describe("QuickActions", () => {
  it("renders both action buttons", () => {
    const onNavigate = vi.fn();
    render(<QuickActions onNavigate={onNavigate} />);
    expect(screen.getByText("View Agents")).toBeInTheDocument();
    expect(screen.getByText("Browse Listings")).toBeInTheDocument();
  });

  it("calls onNavigate with 'agents' when View Agents is clicked", () => {
    const onNavigate = vi.fn();
    render(<QuickActions onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("View Agents"));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith("agents");
  });

  it("calls onNavigate with 'listings' when Browse Listings is clicked", () => {
    const onNavigate = vi.fn();
    render(<QuickActions onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Browse Listings"));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith("listings");
  });

  it("renders buttons as actual button elements", () => {
    const onNavigate = vi.fn();
    render(<QuickActions onNavigate={onNavigate} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
  });

  it("renders icon containers with correct background classes", () => {
    const onNavigate = vi.fn();
    const { container } = render(<QuickActions onNavigate={onNavigate} />);
    const iconContainers = container.querySelectorAll(".rounded-lg.p-1\\.5");
    expect(iconContainers).toHaveLength(2);
  });

  it("applies button styling with border and transition classes", () => {
    const onNavigate = vi.fn();
    const { container } = render(<QuickActions onNavigate={onNavigate} />);
    const buttons = container.querySelectorAll("button");
    for (const button of buttons) {
      expect(button.className).toContain("rounded-xl");
      expect(button.className).toContain("transition-all");
      expect(button.className).toContain("border");
    }
  });

  it("wraps actions in a flex container with gap", () => {
    const onNavigate = vi.fn();
    const { container } = render(<QuickActions onNavigate={onNavigate} />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain("flex");
    expect(wrapper?.className).toContain("gap-3");
  });
});

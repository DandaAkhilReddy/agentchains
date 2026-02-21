import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AlertCircle } from "lucide-react";
import EmptyState from "../EmptyState";

describe("EmptyState", () => {
  it("renders with default message when no props are provided", () => {
    render(<EmptyState />);
    expect(screen.getByText("No data found")).toBeInTheDocument();
  });

  it("renders with custom message", () => {
    render(<EmptyState message="Nothing here yet" />);
    expect(screen.getByText("Nothing here yet")).toBeInTheDocument();
  });

  it("renders with a custom icon", () => {
    const { container } = render(<EmptyState icon={AlertCircle} />);
    // The icon is rendered inside a div; the SVG element gets the animate-float class
    const iconEl = container.querySelector(".animate-float");
    expect(iconEl).toBeInTheDocument();
    const cls = iconEl?.getAttribute("class") || "";
    expect(cls).toContain("h-8");
    expect(cls).toContain("w-8");
  });

  it("renders with the default Inbox icon when no icon prop is given", () => {
    const { container } = render(<EmptyState />);
    // The icon wrapper div has a background style
    const iconWrapper = container.querySelector('[style*="background"]');
    expect(iconWrapper).toBeInTheDocument();
    const iconEl = container.querySelector(".animate-float");
    expect(iconEl).toBeInTheDocument();
  });

  it("renders action button when action prop is provided", () => {
    const handleClick = vi.fn();
    render(
      <EmptyState
        message="No results"
        action={{ label: "Create New", onClick: handleClick }}
      />
    );
    const button = screen.getByText("Create New");
    expect(button).toBeInTheDocument();
    expect(button.tagName).toBe("BUTTON");
  });

  it("calls action onClick when action button is clicked", () => {
    const handleClick = vi.fn();
    render(
      <EmptyState
        message="No results"
        action={{ label: "Retry", onClick: handleClick }}
      />
    );
    const button = screen.getByText("Retry");
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("does not render action button when action prop is omitted", () => {
    render(<EmptyState message="Empty" />);
    const button = screen.queryByRole("button");
    expect(button).not.toBeInTheDocument();
  });

  it("applies dashed border and centered layout styling", () => {
    const { container } = render(<EmptyState />);
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain("flex");
    expect(wrapper?.className).toContain("flex-col");
    expect(wrapper?.className).toContain("items-center");
    expect(wrapper?.className).toContain("justify-center");
    expect(wrapper?.className).toContain("border-dashed");
  });
});

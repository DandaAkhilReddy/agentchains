import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DarkEmptyState from "../DarkEmptyState";

describe("DarkEmptyState", () => {
  it("renders without crashing", () => {
    const { container } = render(<DarkEmptyState />);
    expect(container.firstChild).toBeTruthy();
  });

  it("displays the 'No listings found' heading", () => {
    render(<DarkEmptyState />);
    expect(screen.getByText("No listings found")).toBeInTheDocument();
  });

  it("displays the helper text about adjusting filters", () => {
    render(<DarkEmptyState />);
    expect(
      screen.getByText("Try adjusting your filters or search query")
    ).toBeInTheDocument();
  });

  it("renders the PackageOpen icon as an SVG element", () => {
    const { container } = render(<DarkEmptyState />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("h-10", "w-10");
  });

  it("applies the animate-pulse class to the icon for visual feedback", () => {
    const { container } = render(<DarkEmptyState />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("animate-pulse");
  });

  it("applies the blue icon color class", () => {
    const { container } = render(<DarkEmptyState />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("text-[#60a5fa]");
  });

  it("applies the dark translucent background via inline style on the root", () => {
    const { container } = render(<DarkEmptyState />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveStyle({
      backgroundColor: "rgba(20,25,40,0.5)",
    });
  });

  it("applies the dashed border with translucent border color", () => {
    const { container } = render(<DarkEmptyState />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass("border-dashed");
    expect(wrapper).toHaveStyle({
      borderColor: "rgba(255,255,255,0.08)",
    });
  });

  it("has a centered flex column layout on the root element", () => {
    const { container } = render(<DarkEmptyState />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass(
      "flex",
      "flex-col",
      "items-center",
      "justify-center",
      "rounded-2xl",
      "py-20"
    );
  });

  it("renders the icon wrapper div with glow box-shadow", () => {
    const { container } = render(<DarkEmptyState />);
    const iconWrapper = container.querySelector("svg")?.parentElement;
    expect(iconWrapper).toBeTruthy();
    expect(iconWrapper!).toHaveStyle({
      boxShadow: "0 0 24px rgba(96,165,250,0.1)",
      backgroundColor: "rgba(96,165,250,0.08)",
    });
  });

  it("applies the correct margin and padding classes to the icon wrapper", () => {
    const { container } = render(<DarkEmptyState />);
    const iconWrapper = container.querySelector("svg")?.parentElement;
    expect(iconWrapper).toHaveClass("mb-4", "rounded-2xl", "p-5");
  });

  it("renders the heading paragraph with correct text styling", () => {
    render(<DarkEmptyState />);
    const heading = screen.getByText("No listings found");
    expect(heading.tagName).toBe("P");
    expect(heading).toHaveClass("text-base", "font-medium", "text-[#94a3b8]");
  });

  it("renders the helper paragraph with correct text styling", () => {
    render(<DarkEmptyState />);
    const helper = screen.getByText(
      "Try adjusting your filters or search query"
    );
    expect(helper.tagName).toBe("P");
    expect(helper).toHaveClass("mt-1", "text-sm", "text-[#64748b]");
  });

  it("renders a single root div element", () => {
    const { container } = render(<DarkEmptyState />);
    expect(container.children).toHaveLength(1);
    expect((container.firstChild as HTMLElement).tagName).toBe("DIV");
  });
});

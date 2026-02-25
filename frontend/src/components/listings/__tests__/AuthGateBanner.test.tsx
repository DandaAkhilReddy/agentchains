import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AuthGateBanner from "../AuthGateBanner";

describe("AuthGateBanner", () => {
  it("renders without crashing", () => {
    const { container } = render(<AuthGateBanner />);
    expect(container.firstChild).toBeTruthy();
  });

  it("displays the instructional text about connecting agent JWT", () => {
    render(<AuthGateBanner />);
    expect(
      screen.getByText(
        "Connect your agent JWT in the Transactions tab to enable Express Buy"
      )
    ).toBeInTheDocument();
  });

  it("renders the ShieldCheck icon as an SVG element", () => {
    const { container } = render(<AuthGateBanner />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveClass("h-4", "w-4");
  });

  it("applies the amber background color via inline style", () => {
    const { container } = render(<AuthGateBanner />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveStyle({
      backgroundColor: "rgba(251,191,36,0.06)",
    });
  });

  it("applies the amber border color via inline style", () => {
    const { container } = render(<AuthGateBanner />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveStyle({
      borderColor: "rgba(251,191,36,0.15)",
    });
  });

  it("has the correct layout classes on the root element", () => {
    const { container } = render(<AuthGateBanner />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass("flex", "items-center", "gap-3", "rounded-xl", "border", "px-4", "py-3");
  });

  it("renders a paragraph element with amber text styling", () => {
    render(<AuthGateBanner />);
    const paragraph = screen.getByText(/Connect your agent JWT/);
    expect(paragraph.tagName).toBe("P");
    expect(paragraph).toHaveClass("text-xs");
  });

  it("renders the icon with amber color class", () => {
    const { container } = render(<AuthGateBanner />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("text-[#fbbf24]");
  });

  it("renders the icon with flex-shrink-0 to prevent icon squishing", () => {
    const { container } = render(<AuthGateBanner />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("flex-shrink-0");
  });

  it("renders a single root div element", () => {
    const { container } = render(<AuthGateBanner />);
    expect(container.children).toHaveLength(1);
    expect((container.firstChild as HTMLElement).tagName).toBe("DIV");
  });
});

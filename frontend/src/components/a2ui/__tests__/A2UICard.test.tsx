import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import A2UICard from "../A2UICard";

describe("A2UICard", () => {
  it("renders with title", () => {
    render(<A2UICard data={{ title: "Test Card" }} />);
    expect(screen.getByText("Test Card")).toBeInTheDocument();
  });

  it("renders with subtitle", () => {
    render(<A2UICard data={{ title: "Card", subtitle: "Subtitle text" }} />);
    expect(screen.getByText("Subtitle text")).toBeInTheDocument();
  });

  it("renders with content body", () => {
    render(<A2UICard data={{ content: "Body content here" }} />);
    expect(screen.getByText("Body content here")).toBeInTheDocument();
  });

  it("renders image when provided", () => {
    render(<A2UICard data={{ image: "https://example.com/img.png", image_alt: "Test image" }} />);
    const img = screen.getByAltText("Test image");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/img.png");
  });

  it("uses title as image alt when image_alt is missing", () => {
    render(<A2UICard data={{ title: "My Card", image: "https://example.com/img.png" }} />);
    expect(screen.getByAltText("My Card")).toBeInTheDocument();
  });

  it("uses empty alt when neither image_alt nor title provided", () => {
    render(<A2UICard data={{ image: "https://example.com/img.png" }} />);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("alt", "");
  });

  it("does not render image when not provided", () => {
    render(<A2UICard data={{ title: "No image" }} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("renders action buttons", () => {
    render(<A2UICard data={{ actions: [{ label: "Click Me" }, { label: "Cancel" }] }} />);
    expect(screen.getByText("Click Me")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("opens URL in new tab on action click", () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    render(<A2UICard data={{ actions: [{ label: "Visit", url: "https://example.com" }] }} />);
    fireEvent.click(screen.getByText("Visit"));
    expect(openSpy).toHaveBeenCalledWith("https://example.com", "_blank", "noopener,noreferrer");
    openSpy.mockRestore();
  });

  it("does not open URL when action has no url", () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    render(<A2UICard data={{ actions: [{ label: "Local Action" }] }} />);
    fireEvent.click(screen.getByText("Local Action"));
    expect(openSpy).not.toHaveBeenCalled();
    openSpy.mockRestore();
  });

  it("applies primary style to first action button", () => {
    render(<A2UICard data={{ actions: [{ label: "Primary" }, { label: "Secondary" }] }} />);
    const primary = screen.getByText("Primary");
    expect(primary.className).toContain("bg-[#60a5fa]");
  });

  it("applies primary style when variant is explicitly primary", () => {
    render(<A2UICard data={{ actions: [{ label: "Btn", variant: "secondary" }, { label: "Explicit", variant: "primary" }] }} />);
    const explicit = screen.getByText("Explicit");
    expect(explicit.className).toContain("bg-[#60a5fa]");
  });

  it("renders metadata badges", () => {
    render(<A2UICard data={{}} metadata={{ version: "1.0", status: "active" }} />);
    expect(screen.getByText("1.0")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("does not render metadata section when metadata is empty", () => {
    const { container } = render(<A2UICard data={{}} metadata={{}} />);
    const badges = container.querySelectorAll(".flex.flex-wrap.gap-2");
    expect(badges.length).toBe(0);
  });

  it("does not render metadata section when metadata is undefined", () => {
    const { container } = render(<A2UICard data={{}} />);
    const badges = container.querySelectorAll("span.inline-flex");
    expect(badges.length).toBe(0);
  });

  it("renders all data fields together", () => {
    render(
      <A2UICard
        data={{
          title: "Full Card",
          subtitle: "Sub",
          content: "Body",
          image: "https://example.com/img.png",
          actions: [{ label: "Go" }],
        }}
        metadata={{ key: "val" }}
      />
    );
    expect(screen.getByText("Full Card")).toBeInTheDocument();
    expect(screen.getByText("Sub")).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
    expect(screen.getByRole("img")).toBeInTheDocument();
    expect(screen.getByText("Go")).toBeInTheDocument();
    expect(screen.getByText("val")).toBeInTheDocument();
  });

  it("does not render title section when title is undefined", () => {
    const { container } = render(<A2UICard data={{ content: "No title" }} />);
    expect(container.querySelector("h3")).not.toBeInTheDocument();
  });

  it("does not render subtitle when subtitle is undefined", () => {
    const { container } = render(<A2UICard data={{ title: "Title only" }} />);
    const subtitleEl = container.querySelector(".text-xs.text-\\[\\#64748b\\]");
    expect(subtitleEl).not.toBeInTheDocument();
  });

  it("does not render actions section when actions array is empty", () => {
    render(<A2UICard data={{ actions: [] }} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("applies hover shadow class on card container", () => {
    const { container } = render(<A2UICard data={{ title: "Hover test" }} />);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain("hover:shadow-lg");
  });

  it("renders multiple metadata keys correctly", () => {
    render(<A2UICard data={{}} metadata={{ a: "1", b: "2", c: "3" }} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Spinner from "../Spinner";

describe("Spinner", () => {
  it("renders the spinner element with status role", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner).toBeInTheDocument();
  });

  it("has an accessible aria-label defaulting to Loading", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner).toHaveAttribute("aria-label", "Loading");
  });

  it("uses custom label for aria-label and displays label text", () => {
    render(<Spinner label="Fetching data" />);
    const spinner = screen.getByRole("status");
    expect(spinner).toHaveAttribute("aria-label", "Fetching data");
    expect(screen.getByText("Fetching data")).toBeInTheDocument();
  });

  it("applies sm size classes", () => {
    render(<Spinner size="sm" />);
    const spinner = screen.getByRole("status");
    expect(spinner.className).toContain("h-4");
    expect(spinner.className).toContain("w-4");
    expect(spinner.className).toContain("border-[1.5px]");
  });

  it("applies md size classes by default", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner.className).toContain("h-5");
    expect(spinner.className).toContain("w-5");
    expect(spinner.className).toContain("border-2");
  });

  it("applies lg size classes", () => {
    render(<Spinner size="lg" />);
    const spinner = screen.getByRole("status");
    expect(spinner.className).toContain("h-8");
    expect(spinner.className).toContain("w-8");
    expect(spinner.className).toContain("border-[3px]");
  });

  it("applies animate-spin class for spinning animation", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner.className).toContain("animate-spin");
  });

  it("applies glow box-shadow style", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status");
    expect(spinner.getAttribute("style")).toContain("box-shadow");
  });

  it("does not display label text when label prop is omitted", () => {
    const { container } = render(<Spinner />);
    const span = container.querySelector("span");
    expect(span).not.toBeInTheDocument();
  });
});

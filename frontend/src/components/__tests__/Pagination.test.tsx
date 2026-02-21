import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Pagination from "../Pagination";

describe("Pagination", () => {
  it("renders pagination controls", () => {
    render(<Pagination page={1} totalPages={5} onPageChange={() => {}} />);
    expect(screen.getByLabelText("First page")).toBeInTheDocument();
    expect(screen.getByLabelText("Previous page")).toBeInTheDocument();
    expect(screen.getByLabelText("Next page")).toBeInTheDocument();
    expect(screen.getByLabelText("Last page")).toBeInTheDocument();
  });

  it("returns null when totalPages is 1 or less", () => {
    const { container } = render(
      <Pagination page={1} totalPages={1} onPageChange={() => {}} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("shows current page number in info text", () => {
    render(<Pagination page={3} totalPages={10} onPageChange={() => {}} />);
    expect(screen.getByText("Page 3 of 10")).toBeInTheDocument();
  });

  it("calls onPageChange with 1 when first page button is clicked", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={5} totalPages={10} onPageChange={onPageChange} />);
    await user.click(screen.getByLabelText("First page"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  it("calls onPageChange with page-1 when previous page button is clicked", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={5} totalPages={10} onPageChange={onPageChange} />);
    await user.click(screen.getByLabelText("Previous page"));
    expect(onPageChange).toHaveBeenCalledWith(4);
  });

  it("calls onPageChange with page+1 when next page button is clicked", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={5} totalPages={10} onPageChange={onPageChange} />);
    await user.click(screen.getByLabelText("Next page"));
    expect(onPageChange).toHaveBeenCalledWith(6);
  });

  it("calls onPageChange with totalPages when last page button is clicked", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={5} totalPages={10} onPageChange={onPageChange} />);
    await user.click(screen.getByLabelText("Last page"));
    expect(onPageChange).toHaveBeenCalledWith(10);
  });

  it("disables first and previous buttons on page 1", () => {
    render(<Pagination page={1} totalPages={5} onPageChange={() => {}} />);
    expect(screen.getByLabelText("First page")).toBeDisabled();
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
    expect(screen.getByLabelText("Next page")).not.toBeDisabled();
    expect(screen.getByLabelText("Last page")).not.toBeDisabled();
  });

  it("disables next and last buttons on the last page", () => {
    render(<Pagination page={5} totalPages={5} onPageChange={() => {}} />);
    expect(screen.getByLabelText("Next page")).toBeDisabled();
    expect(screen.getByLabelText("Last page")).toBeDisabled();
    expect(screen.getByLabelText("First page")).not.toBeDisabled();
    expect(screen.getByLabelText("Previous page")).not.toBeDisabled();
  });

  it("shows ellipsis when there are many pages", () => {
    const { container } = render(
      <Pagination page={5} totalPages={20} onPageChange={() => {}} />
    );
    const ellipses = container.querySelectorAll("span");
    // Filter spans that contain "..." (excluding the "Page X of Y" span)
    const dots = Array.from(ellipses).filter((s) => s.textContent === "...");
    expect(dots.length).toBeGreaterThanOrEqual(1);
  });

  it("calls onPageChange with the correct page when a page number button is clicked", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={1} totalPages={5} onPageChange={onPageChange} />);
    await user.click(screen.getByText("3"));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });
});

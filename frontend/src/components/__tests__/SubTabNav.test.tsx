import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SubTabNav from "../SubTabNav";

const sampleTabs = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "inactive", label: "Inactive" },
];

describe("SubTabNav", () => {
  it("renders all sub-tab labels", () => {
    const onChange = vi.fn();
    render(<SubTabNav tabs={sampleTabs} active="all" onChange={onChange} />);

    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("highlights the active sub-tab with active styles", () => {
    const onChange = vi.fn();
    render(<SubTabNav tabs={sampleTabs} active="active" onChange={onChange} />);

    const activeButton = screen.getByText("Active").closest("button");
    expect(activeButton?.className).toContain("text-[#60a5fa]");
    expect(activeButton?.className).toContain("bg-[rgba(96,165,250,0.1)]");

    const inactiveButton = screen.getByText("All").closest("button");
    expect(inactiveButton?.className).toContain("text-[#64748b]");
    expect(inactiveButton?.className).toContain("bg-transparent");
  });

  it("calls onChange with the correct tab id when clicked", () => {
    const onChange = vi.fn();
    render(<SubTabNav tabs={sampleTabs} active="all" onChange={onChange} />);

    fireEvent.click(screen.getByText("Inactive"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("inactive");
  });

  it("calls onChange for each sub-tab click", () => {
    const onChange = vi.fn();
    render(<SubTabNav tabs={sampleTabs} active="all" onChange={onChange} />);

    fireEvent.click(screen.getByText("Active"));
    fireEvent.click(screen.getByText("Inactive"));
    fireEvent.click(screen.getByText("All"));

    expect(onChange).toHaveBeenCalledTimes(3);
    expect(onChange).toHaveBeenNthCalledWith(1, "active");
    expect(onChange).toHaveBeenNthCalledWith(2, "inactive");
    expect(onChange).toHaveBeenNthCalledWith(3, "all");
  });

  it("handles a single sub-tab", () => {
    const onChange = vi.fn();
    const singleTab = [{ id: "only", label: "Only" }];
    render(<SubTabNav tabs={singleTab} active="only" onChange={onChange} />);

    expect(screen.getByText("Only")).toBeInTheDocument();
    const button = screen.getByText("Only").closest("button");
    expect(button?.className).toContain("text-[#60a5fa]");
  });

  it("renders buttons for each tab", () => {
    const onChange = vi.fn();
    const { container } = render(
      <SubTabNav tabs={sampleTabs} active="all" onChange={onChange} />
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(3);
  });

  it("applies rounded-lg styling to sub-tab buttons", () => {
    const onChange = vi.fn();
    const { container } = render(
      <SubTabNav tabs={sampleTabs} active="all" onChange={onChange} />
    );
    const buttons = container.querySelectorAll("button");
    buttons.forEach((button) => {
      expect(button.className).toContain("rounded-lg");
    });
  });

  it("works alongside TabNav context (renders independently)", () => {
    const onTabChange = vi.fn();
    const onSubTabChange = vi.fn();

    // SubTabNav is a standalone component, verify it renders fine in isolation
    const { container } = render(
      <div>
        <SubTabNav tabs={sampleTabs} active="active" onChange={onSubTabChange} />
      </div>
    );

    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();

    fireEvent.click(screen.getByText("All"));
    expect(onSubTabChange).toHaveBeenCalledWith("all");
    expect(onTabChange).not.toHaveBeenCalled();
  });
});

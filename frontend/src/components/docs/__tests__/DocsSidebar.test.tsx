import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DocsSidebar from "../DocsSidebar";

const sections = [
  { id: "getting-started", title: "Getting Started" },
  { id: "authentication", title: "Authentication" },
  { id: "agents", title: "Agents" },
  { id: "listings", title: "Listings" },
];

const groups = [
  { label: "Overview", sectionIds: ["getting-started", "authentication"] },
  { label: "Resources", sectionIds: ["agents", "listings"] },
];

const defaultProps = {
  sections,
  activeId: "getting-started",
  onSelect: vi.fn(),
  searchQuery: "",
  onSearch: vi.fn(),
};

describe("DocsSidebar", () => {
  it("renders search input with placeholder", () => {
    render(<DocsSidebar {...defaultProps} />);
    expect(screen.getByPlaceholderText("Search docs...")).toBeInTheDocument();
  });

  it("renders all sections in flat mode when groups is not provided", () => {
    render(<DocsSidebar {...defaultProps} />);
    expect(screen.getByText("Getting Started")).toBeInTheDocument();
    expect(screen.getByText("Authentication")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Listings")).toBeInTheDocument();
  });

  it("renders group labels when groups prop is provided", () => {
    render(<DocsSidebar {...defaultProps} groups={groups} />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Resources")).toBeInTheDocument();
  });

  it("renders sections within their respective groups", () => {
    render(<DocsSidebar {...defaultProps} groups={groups} />);
    expect(screen.getByText("Getting Started")).toBeInTheDocument();
    expect(screen.getByText("Authentication")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Listings")).toBeInTheDocument();
  });

  it("calls onSelect with the correct section id when a section button is clicked", () => {
    const onSelect = vi.fn();
    render(<DocsSidebar {...defaultProps} onSelect={onSelect} />);

    fireEvent.click(screen.getByText("Authentication"));
    expect(onSelect).toHaveBeenCalledWith("authentication");
  });

  it("applies active styling to the active section", () => {
    render(<DocsSidebar {...defaultProps} activeId="agents" />);

    const activeBtn = screen.getByText("Agents");
    expect(activeBtn.className).toContain("text-[#60a5fa]");

    const inactiveBtn = screen.getByText("Getting Started");
    expect(inactiveBtn.className).toContain("text-[#64748b]");
  });

  it("filters sections based on search query in flat mode", () => {
    render(<DocsSidebar {...defaultProps} searchQuery="auth" />);
    expect(screen.getByText("Authentication")).toBeInTheDocument();
    expect(screen.queryByText("Agents")).not.toBeInTheDocument();
    expect(screen.queryByText("Listings")).not.toBeInTheDocument();
  });

  it("filters sections within groups based on search query", () => {
    render(
      <DocsSidebar {...defaultProps} groups={groups} searchQuery="agent" />,
    );
    expect(screen.getByText("Agents")).toBeInTheDocument();
    // "Overview" group should be hidden because no sections match
    expect(screen.queryByText("Overview")).not.toBeInTheDocument();
    // "Resources" group should remain because "Agents" matches
    expect(screen.getByText("Resources")).toBeInTheDocument();
  });

  it("hides groups entirely when no sections match the search", () => {
    render(
      <DocsSidebar
        {...defaultProps}
        groups={groups}
        searchQuery="nonexistent"
      />,
    );
    expect(screen.queryByText("Overview")).not.toBeInTheDocument();
    expect(screen.queryByText("Resources")).not.toBeInTheDocument();
  });

  it("calls onSearch when the search input value changes", () => {
    const onSearch = vi.fn();
    render(<DocsSidebar {...defaultProps} onSearch={onSearch} />);

    const input = screen.getByPlaceholderText("Search docs...");
    fireEvent.change(input, { target: { value: "test" } });

    expect(onSearch).toHaveBeenCalledWith("test");
  });

  it("search filtering is case-insensitive", () => {
    render(<DocsSidebar {...defaultProps} searchQuery="GETTING" />);
    expect(screen.getByText("Getting Started")).toBeInTheDocument();
    expect(screen.queryByText("Authentication")).not.toBeInTheDocument();
  });
});

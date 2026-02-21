import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import A2UITable from "../A2UITable";

describe("A2UITable", () => {
  it("renders empty state when no data provided", () => {
    render(<A2UITable data={{}} />);
    expect(screen.getByText("No table data provided.")).toBeInTheDocument();
  });

  it("renders empty state with empty headers and rows", () => {
    render(<A2UITable data={{ headers: [], rows: [] }} />);
    expect(screen.getByText("No table data provided.")).toBeInTheDocument();
  });

  it("renders table with headers", () => {
    render(<A2UITable data={{ headers: ["Name", "Age", "City"], rows: [] }} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Age")).toBeInTheDocument();
    expect(screen.getByText("City")).toBeInTheDocument();
  });

  it("renders table rows", () => {
    render(
      <A2UITable
        data={{
          headers: ["Name", "Score"],
          rows: [["Alice", 95], ["Bob", 87]],
        }}
      />
    );
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
  });

  it("renders title when provided", () => {
    render(<A2UITable data={{ title: "Score Table", headers: ["Name"], rows: [["Alice"]] }} />);
    expect(screen.getByText("Score Table")).toBeInTheDocument();
  });

  it("renders caption when provided", () => {
    render(
      <A2UITable
        data={{ title: "Table", caption: "Updated daily", headers: ["Col"], rows: [["val"]] }}
      />
    );
    expect(screen.getByText("Updated daily")).toBeInTheDocument();
  });

  it("does not render title section when title is missing", () => {
    const { container } = render(
      <A2UITable data={{ headers: ["Col"], rows: [["val"]] }} />
    );
    expect(container.querySelector("h3")).not.toBeInTheDocument();
  });

  it("sorts string column ascending on header click", () => {
    render(
      <A2UITable
        data={{
          headers: ["Name"],
          rows: [["Charlie"], ["Alice"], ["Bob"]],
        }}
      />
    );
    fireEvent.click(screen.getByText("Name"));
    const cells = screen.getAllByRole("cell");
    expect(cells[0].textContent).toBe("Alice");
    expect(cells[1].textContent).toBe("Bob");
    expect(cells[2].textContent).toBe("Charlie");
  });

  it("toggles sort direction on second header click", () => {
    render(
      <A2UITable
        data={{
          headers: ["Name"],
          rows: [["Charlie"], ["Alice"], ["Bob"]],
        }}
      />
    );
    const header = screen.getByText("Name");
    fireEvent.click(header); // ascending
    fireEvent.click(header); // descending
    const cells = screen.getAllByRole("cell");
    expect(cells[0].textContent).toBe("Charlie");
    expect(cells[2].textContent).toBe("Alice");
  });

  it("sorts numeric columns correctly", () => {
    render(
      <A2UITable
        data={{
          headers: ["Score"],
          rows: [[30], [10], [20]],
        }}
      />
    );
    fireEvent.click(screen.getByText("Score"));
    const cells = screen.getAllByRole("cell");
    expect(cells[0].textContent).toBe("10");
    expect(cells[1].textContent).toBe("20");
    expect(cells[2].textContent).toBe("30");
  });

  it("shows sort indicator arrow on sorted column", () => {
    render(
      <A2UITable data={{ headers: ["Col"], rows: [["a"], ["b"]] }} />
    );
    fireEvent.click(screen.getByText("Col"));
    expect(screen.getByText("\u2191")).toBeInTheDocument();
  });

  it("shows descending arrow after toggling", () => {
    render(
      <A2UITable data={{ headers: ["Col"], rows: [["a"], ["b"]] }} />
    );
    const header = screen.getByText("Col");
    fireEvent.click(header);
    fireEvent.click(header);
    expect(screen.getByText("\u2193")).toBeInTheDocument();
  });

  it("renders metadata footer when metadata is provided", () => {
    render(
      <A2UITable
        data={{ headers: ["Col"], rows: [["val"]] }}
        metadata={{ source: "api", count: "3" }}
      />
    );
    expect(screen.getByText("api")).toBeInTheDocument();
  });

  it("does not render metadata footer when metadata is empty", () => {
    const { container } = render(
      <A2UITable data={{ headers: ["Col"], rows: [["val"]] }} metadata={{}} />
    );
    const footers = container.querySelectorAll(".border-t");
    expect(footers.length).toBe(0);
  });

  it("renders table element with correct structure", () => {
    const { container } = render(
      <A2UITable
        data={{ headers: ["A", "B"], rows: [["1", "2"]] }}
      />
    );
    expect(container.querySelector("table")).toBeInTheDocument();
    expect(container.querySelector("thead")).toBeInTheDocument();
    expect(container.querySelector("tbody")).toBeInTheDocument();
  });

  it("renders correct number of rows", () => {
    render(
      <A2UITable
        data={{
          headers: ["Name"],
          rows: [["A"], ["B"], ["C"], ["D"]],
        }}
      />
    );
    const rows = screen.getAllByRole("row");
    // 1 header row + 4 data rows
    expect(rows.length).toBe(5);
  });

  it("handles rows without headers", () => {
    render(<A2UITable data={{ rows: [["data1"], ["data2"]] }} />);
    expect(screen.getByText("data1")).toBeInTheDocument();
    expect(screen.getByText("data2")).toBeInTheDocument();
  });

  it("resets sort when clicking a different column", () => {
    render(
      <A2UITable
        data={{
          headers: ["Name", "Age"],
          rows: [["Bob", 25], ["Alice", 30]],
        }}
      />
    );
    fireEvent.click(screen.getByText("Name"));
    fireEvent.click(screen.getByText("Age"));
    const cells = screen.getAllByRole("cell");
    expect(cells[1].textContent).toBe("25");
  });
});

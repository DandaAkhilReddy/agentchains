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

  it("sort returns 0 for equal string values (line 48 return 0 branch)", () => {
    // When strA === strB the sort comparator returns 0 (stable — no reordering).
    // Use duplicate string values so the branch at line 48 is hit.
    render(
      <A2UITable
        data={{
          headers: ["Name", "Score"],
          rows: [["Alice", 90], ["Alice", 85], ["Bob", 80]],
        }}
      />
    );
    fireEvent.click(screen.getByText("Name")); // sort ascending by Name
    // "Alice" appears twice — the two Alice rows have equal strA===strB, return 0.
    // "Bob" should be last.
    const cells = screen.getAllByRole("cell");
    // Rows in order: Alice/90, Alice/85, Bob/80 (or Alice/85, Alice/90, Bob/80 — both valid)
    // The important thing: Bob is last and the component doesn't crash.
    const nameValues = cells
      .filter((_, i) => i % 2 === 0)
      .map((c) => c.textContent);
    expect(nameValues.filter((n) => n === "Alice").length).toBe(2);
    expect(nameValues[nameValues.length - 1]).toBe("Bob");
  });

  it("sort returns 0 for equal numeric values preserving relative order (numeric branch line 42)", () => {
    // Equal numbers → valA - valB === 0 → returns 0 in the numeric branch (line 42)
    render(
      <A2UITable
        data={{
          headers: ["Score"],
          rows: [[100], [100], [50]],
        }}
      />
    );
    fireEvent.click(screen.getByText("Score")); // sort ascending
    const cells = screen.getAllByRole("cell");
    // 50 should be first; the two 100s follow in some order
    expect(cells[0].textContent).toBe("50");
    expect(cells[1].textContent).toBe("100");
    expect(cells[2].textContent).toBe("100");
  });

  it("handleSort does nothing when isSortable is false (covers !isSortable early return)", () => {
    // isSortable = sortable !== false && headers.length > 0
    // If sortable=false, header clicks do nothing.
    render(
      <A2UITable
        data={{
          sortable: false,
          headers: ["Name"],
          rows: [["Charlie"], ["Alice"]],
        }}
      />
    );
    fireEvent.click(screen.getByText("Name"));
    // Rows remain in original order (no sort arrow, no reorder)
    const cells = screen.getAllByRole("cell");
    expect(cells[0].textContent).toBe("Charlie");
    expect(cells[1].textContent).toBe("Alice");
    // No sort indicator arrow
    expect(document.querySelector("span.text-\\[\\#60a5fa\\]")).toBeNull();
  });

  it("sorts numeric column descending when sort toggled twice (covers line 42: sortAsc false branch valB - valA)", () => {
    // Click twice on Score header: first click → ascending, second click → descending.
    // Descending numeric sort hits `valB - valA` at line 42 (sortAsc=false branch).
    render(
      <A2UITable
        data={{
          headers: ["Score"],
          rows: [[10], [30], [20]],
        }}
      />
    );
    const header = screen.getByText("Score");
    fireEvent.click(header); // ascending: 10, 20, 30
    fireEvent.click(header); // descending: 30, 20, 10 — hits valB - valA branch
    const cells = screen.getAllByRole("cell");
    expect(cells[0].textContent).toBe("30");
    expect(cells[1].textContent).toBe("20");
    expect(cells[2].textContent).toBe("10");
  });

  it("sort handles undefined/null cell values using ?? '' fallback (covers lines 39-40)", () => {
    // When a row has fewer cells than the sort column index, a[sortCol] is undefined.
    // The `?? ""` fallback at lines 39-40 converts it to "".
    // Use rows where the first row has a missing cell for column 1.
    render(
      <A2UITable
        data={{
          headers: ["Name", "Score"],
          rows: [
            ["Alice"],       // row[1] is undefined → ?? "" → ""
            ["Bob", 50],
          ],
        }}
      />
    );
    // Click the "Score" header to trigger sort on column 1
    fireEvent.click(screen.getByText("Score"));
    // Alice (value "") sorts before Bob (value 50) in ascending string comparison
    // The important thing: the component renders without crashing
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });
});

import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import DataTable, { type Column } from "../DataTable";

// Test data types
interface TestUser {
  id: string;
  name: string;
  email: string;
  age: number;
}

interface TestProduct {
  productId: number;
  title: string;
  price: number;
}

describe("DataTable", () => {
  // Sample data and columns for testing
  const testUsers: TestUser[] = [
    { id: "user-1", name: "Alice", email: "alice@example.com", age: 25 },
    { id: "user-2", name: "Bob", email: "bob@example.com", age: 30 },
    { id: "user-3", name: "Charlie", email: "charlie@example.com", age: 35 },
  ];

  const userColumns: Column<TestUser>[] = [
    {
      key: "name",
      header: "Name",
      render: (user) => user.name,
    },
    {
      key: "email",
      header: "Email Address",
      render: (user) => user.email,
    },
    {
      key: "age",
      header: "Age",
      render: (user) => user.age.toString(),
    },
  ];

  const userKeyFn = (user: TestUser) => user.id;

  test("loading state shows spinner", () => {
    render(
      <DataTable
        columns={userColumns}
        data={[]}
        isLoading={true}
        keyFn={userKeyFn}
      />
    );

    // Spinner has specific className with animate-spin
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass("rounded-full");
  });

  test("empty data shows EmptyState with default message", () => {
    render(
      <DataTable
        columns={userColumns}
        data={[]}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // EmptyState shows the empty symbol and message
    expect(screen.getByText("∅")).toBeInTheDocument();
    expect(screen.getByText("No data found")).toBeInTheDocument();
  });

  test("custom empty message is displayed", () => {
    const customMessage = "No users available at this time";
    render(
      <DataTable
        columns={userColumns}
        data={[]}
        isLoading={false}
        keyFn={userKeyFn}
        emptyMessage={customMessage}
      />
    );

    expect(screen.getByText("∅")).toBeInTheDocument();
    expect(screen.getByText(customMessage)).toBeInTheDocument();
  });

  test("renders column headers correctly", () => {
    render(
      <DataTable
        columns={userColumns}
        data={testUsers}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Check all column headers are rendered
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Email Address")).toBeInTheDocument();
    expect(screen.getByText("Age")).toBeInTheDocument();

    // Headers should be in <th> elements
    const nameHeader = screen.getByText("Name").closest("th");
    expect(nameHeader).toBeInTheDocument();
  });

  test("renders data rows correctly", () => {
    render(
      <DataTable
        columns={userColumns}
        data={testUsers}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Check all user names are rendered
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();

    // Check emails are rendered
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();

    // Check ages are rendered
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("35")).toBeInTheDocument();
  });

  test("cell render function works with complex rendering", () => {
    const columnsWithComplexRender: Column<TestUser>[] = [
      {
        key: "name",
        header: "Name",
        render: (user) => <strong data-testid="user-name">{user.name}</strong>,
      },
      {
        key: "email",
        header: "Email",
        render: (user) => (
          <a href={`mailto:${user.email}`} data-testid="user-email">
            {user.email}
          </a>
        ),
      },
    ];

    render(
      <DataTable
        columns={columnsWithComplexRender}
        data={[testUsers[0]]}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Check that custom render functions work
    const nameElement = screen.getByTestId("user-name");
    expect(nameElement).toBeInTheDocument();
    expect(nameElement.tagName).toBe("STRONG");
    expect(nameElement).toHaveTextContent("Alice");

    const emailElement = screen.getByTestId("user-email");
    expect(emailElement).toBeInTheDocument();
    expect(emailElement.tagName).toBe("A");
    expect(emailElement).toHaveAttribute("href", "mailto:alice@example.com");
  });

  test("column className is applied correctly", () => {
    const columnsWithClassName: Column<TestUser>[] = [
      {
        key: "name",
        header: "Name",
        render: (user) => user.name,
        className: "font-bold text-blue-500",
      },
      {
        key: "email",
        header: "Email",
        render: (user) => user.email,
        className: "text-sm italic",
      },
      {
        key: "age",
        header: "Age",
        render: (user) => user.age.toString(),
        // No className for this column
      },
    ];

    const { container } = render(
      <DataTable
        columns={columnsWithClassName}
        data={[testUsers[0]]}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Check header className
    const nameHeader = screen.getByText("Name").closest("th");
    expect(nameHeader).toHaveClass("font-bold", "text-blue-500");

    const emailHeader = screen.getByText("Email").closest("th");
    expect(emailHeader).toHaveClass("text-sm", "italic");

    // Check cell className
    const nameCell = screen.getByText("Alice").closest("td");
    expect(nameCell).toHaveClass("font-bold", "text-blue-500");

    const emailCell = screen.getByText("alice@example.com").closest("td");
    expect(emailCell).toHaveClass("text-sm", "italic");

    // Age column should not have custom classes (only default px-4 py-3)
    const ageCell = screen.getByText("25").closest("td");
    expect(ageCell).toHaveClass("px-4", "py-3");
    expect(ageCell).not.toHaveClass("font-bold");
  });

  test("keyFn generates unique keys for rows", () => {
    const { container } = render(
      <DataTable
        columns={userColumns}
        data={testUsers}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Get all tbody rows (excludes header row)
    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(3);

    // Each row should have been keyed by keyFn
    // We can't directly check React keys, but we can verify all rows are rendered
    expect(rows[0]).toHaveTextContent("Alice");
    expect(rows[1]).toHaveTextContent("Bob");
    expect(rows[2]).toHaveTextContent("Charlie");
  });

  test("handles zero rows gracefully", () => {
    render(
      <DataTable
        columns={userColumns}
        data={[]}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Should show empty state, not a table
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("∅")).toBeInTheDocument();
  });

  test("renders table structure correctly with multiple rows", () => {
    const { container } = render(
      <DataTable
        columns={userColumns}
        data={testUsers}
        isLoading={false}
        keyFn={userKeyFn}
      />
    );

    // Check table structure
    const table = container.querySelector("table");
    expect(table).toBeInTheDocument();
    expect(table).toHaveClass("w-full", "text-sm");

    const thead = container.querySelector("thead");
    expect(thead).toBeInTheDocument();

    const tbody = container.querySelector("tbody");
    expect(tbody).toBeInTheDocument();

    // Verify correct number of header cells
    const headerCells = container.querySelectorAll("thead th");
    expect(headerCells).toHaveLength(3);

    // Verify correct number of data rows
    const dataRows = container.querySelectorAll("tbody tr");
    expect(dataRows).toHaveLength(3);

    // Each row should have 3 cells (one per column)
    dataRows.forEach((row) => {
      const cells = row.querySelectorAll("td");
      expect(cells).toHaveLength(3);
    });
  });

  test("works with different data types", () => {
    const testProducts: TestProduct[] = [
      { productId: 101, title: "Laptop", price: 999.99 },
      { productId: 102, title: "Mouse", price: 29.99 },
    ];

    const productColumns: Column<TestProduct>[] = [
      {
        key: "id",
        header: "ID",
        render: (product) => product.productId.toString(),
      },
      {
        key: "title",
        header: "Product",
        render: (product) => product.title,
      },
      {
        key: "price",
        header: "Price",
        render: (product) => `$${product.price.toFixed(2)}`,
      },
    ];

    render(
      <DataTable
        columns={productColumns}
        data={testProducts}
        isLoading={false}
        keyFn={(product) => `product-${product.productId}`}
      />
    );

    // Verify products are rendered
    expect(screen.getByText("101")).toBeInTheDocument();
    expect(screen.getByText("Laptop")).toBeInTheDocument();
    expect(screen.getByText("$999.99")).toBeInTheDocument();
    expect(screen.getByText("Mouse")).toBeInTheDocument();
    expect(screen.getByText("$29.99")).toBeInTheDocument();
  });
});

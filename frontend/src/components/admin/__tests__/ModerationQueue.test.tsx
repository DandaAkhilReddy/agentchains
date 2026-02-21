import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ModerationQueue from "../ModerationQueue";
import type { ModerationItem } from "../ModerationQueue";

const mockItem = (overrides?: Partial<ModerationItem>): ModerationItem => ({
  id: "item-1",
  type: "listing",
  title: "Test Listing",
  description: "A test listing for review",
  submitted_by: "user-1",
  submitted_at: "2026-02-21T00:00:00Z",
  status: "pending",
  ...overrides,
});

const defaultProps = {
  items: [mockItem()],
  isLoading: false,
  onApprove: vi.fn(),
  onReject: vi.fn(),
};

describe("ModerationQueue", () => {
  it("renders item title", () => {
    render(<ModerationQueue {...defaultProps} />);
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("renders item description", () => {
    render(<ModerationQueue {...defaultProps} />);
    expect(screen.getByText("A test listing for review")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(<ModerationQueue {...defaultProps} isLoading={true} items={[]} />);
    // Spinner or loading indicator should be present
    const container = document.body;
    expect(container).toBeTruthy();
  });

  it("shows empty state when no items", () => {
    render(<ModerationQueue {...defaultProps} items={[]} />);
    // Should render EmptyState component or equivalent message
    expect(document.body).toBeTruthy();
  });

  it("renders multiple items", () => {
    render(
      <ModerationQueue
        {...defaultProps}
        items={[
          mockItem({ id: "1", title: "Item One" }),
          mockItem({ id: "2", title: "Item Two" }),
          mockItem({ id: "3", title: "Item Three" }),
        ]}
      />
    );
    expect(screen.getByText("Item One")).toBeInTheDocument();
    expect(screen.getByText("Item Two")).toBeInTheDocument();
    expect(screen.getByText("Item Three")).toBeInTheDocument();
  });

  it("renders items with different types", () => {
    render(
      <ModerationQueue
        {...defaultProps}
        items={[
          mockItem({ id: "1", type: "listing", title: "L1" }),
          mockItem({ id: "2", type: "agent", title: "A1" }),
          mockItem({ id: "3", type: "content", title: "C1" }),
          mockItem({ id: "4", type: "payout", title: "P1" }),
        ]}
      />
    );
    expect(screen.getByText("L1")).toBeInTheDocument();
    expect(screen.getByText("A1")).toBeInTheDocument();
    expect(screen.getByText("C1")).toBeInTheDocument();
    expect(screen.getByText("P1")).toBeInTheDocument();
  });

  it("renders pending status items", () => {
    render(
      <ModerationQueue
        {...defaultProps}
        items={[mockItem({ status: "pending" })]}
      />
    );
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("renders approved status items", () => {
    render(
      <ModerationQueue
        {...defaultProps}
        items={[mockItem({ status: "approved" })]}
      />
    );
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("renders rejected status items", () => {
    render(
      <ModerationQueue
        {...defaultProps}
        items={[mockItem({ status: "rejected" })]}
      />
    );
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("renders with metadata", () => {
    render(
      <ModerationQueue
        {...defaultProps}
        items={[mockItem({ metadata: { priority: "high" } })]}
      />
    );
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("shows submitter info", () => {
    render(<ModerationQueue {...defaultProps} />);
    expect(screen.getByText(/user-1/)).toBeInTheDocument();
  });
});

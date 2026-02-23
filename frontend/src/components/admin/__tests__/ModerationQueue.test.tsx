import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
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

describe("ModerationQueue", () => {
  let onApprove: ReturnType<typeof vi.fn>;
  let onReject: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onApprove = vi.fn();
    onReject = vi.fn();
  });

  function renderQueue(
    overrides: Partial<Parameters<typeof ModerationQueue>[0]> = {}
  ) {
    const defaultProps = {
      items: [mockItem()],
      isLoading: false,
      onApprove,
      onReject,
    };
    return render(<ModerationQueue {...defaultProps} {...overrides} />);
  }

  /* ------------------------------------------------------------------ */
  /* Basic rendering                                                     */
  /* ------------------------------------------------------------------ */

  it("renders item title", () => {
    renderQueue();
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("renders item description", () => {
    renderQueue();
    expect(screen.getByText("A test listing for review")).toBeInTheDocument();
  });

  it("renders the header with Moderation Queue text", () => {
    renderQueue();
    expect(screen.getByText("Moderation Queue")).toBeInTheDocument();
  });

  it("shows submitter info", () => {
    renderQueue();
    expect(screen.getByText(/user-1/)).toBeInTheDocument();
  });

  it("shows truncated item ID", () => {
    renderQueue({ items: [mockItem({ id: "abcdefgh-1234-5678" })] });
    expect(screen.getByText("abcdefgh")).toBeInTheDocument();
  });

  it("renders the submitted_at date", () => {
    renderQueue();
    // The date is formatted with toLocaleString
    const dateEl = screen.getByText(/2026/);
    expect(dateEl).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Loading state                                                       */
  /* ------------------------------------------------------------------ */

  it("shows loading spinner when isLoading is true", () => {
    renderQueue({ isLoading: true, items: [] });
    expect(screen.getByText("Loading moderation queue...")).toBeInTheDocument();
  });

  it("does not render items when loading", () => {
    renderQueue({ isLoading: true, items: [mockItem()] });
    expect(screen.queryByText("Test Listing")).not.toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Empty state                                                         */
  /* ------------------------------------------------------------------ */

  it("shows empty state when no items after filtering", () => {
    renderQueue({ items: [] });
    expect(
      screen.getByText("No items in the moderation queue.")
    ).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Pending count display                                               */
  /* ------------------------------------------------------------------ */

  it("shows correct pending count for 1 pending item", () => {
    renderQueue({ items: [mockItem({ status: "pending" })] });
    expect(screen.getByText("1 item pending review")).toBeInTheDocument();
  });

  it("shows correct pending count for multiple pending items", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", status: "pending" }),
        mockItem({ id: "2", status: "pending" }),
        mockItem({ id: "3", status: "approved" }),
      ],
    });
    expect(screen.getByText("2 items pending review")).toBeInTheDocument();
  });

  it("shows 0 items pending when none are pending", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", status: "approved" }),
        mockItem({ id: "2", status: "rejected" }),
      ],
    });
    expect(screen.getByText("0 items pending review")).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Type labels and status badges                                       */
  /* ------------------------------------------------------------------ */

  it("renders type label badges for each item type", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", type: "listing", title: "L1" }),
        mockItem({ id: "2", type: "agent", title: "A1" }),
        mockItem({ id: "3", type: "content", title: "C1" }),
        mockItem({ id: "4", type: "payout", title: "P1" }),
      ],
    });
    // "Listing" badge text
    expect(screen.getByText("Listing")).toBeInTheDocument();
    // "Agent" badge - use getAllByText because "Agents" option is similar
    expect(screen.getByText("Agent")).toBeInTheDocument();
    // "Content" appears both in the filter option and the type badge, so use getAllByText
    const contentElements = screen.getAllByText("Content");
    expect(contentElements.length).toBeGreaterThanOrEqual(2); // option + badge
    // "Payout" badge text
    expect(screen.getByText("Payout")).toBeInTheDocument();
  });

  it("renders status label badges", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", status: "pending", title: "Pending Item" }),
        mockItem({ id: "2", status: "approved", title: "Approved Item" }),
        mockItem({ id: "3", status: "rejected", title: "Rejected Item" }),
      ],
    });
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Filter dropdown                                                     */
  /* ------------------------------------------------------------------ */

  it("renders the filter dropdown with All Types selected by default", () => {
    renderQueue();
    const select = screen.getByDisplayValue("All Types");
    expect(select).toBeInTheDocument();
  });

  it("filters items by type when a specific filter is selected", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", type: "listing", title: "My Listing" }),
        mockItem({ id: "2", type: "agent", title: "My Agent" }),
        mockItem({ id: "3", type: "content", title: "My Content" }),
      ],
    });

    const select = screen.getByDisplayValue("All Types");

    // Filter to agents only
    fireEvent.change(select, { target: { value: "agent" } });
    expect(screen.getByText("My Agent")).toBeInTheDocument();
    expect(screen.queryByText("My Listing")).not.toBeInTheDocument();
    expect(screen.queryByText("My Content")).not.toBeInTheDocument();
  });

  it("shows all items when filter is reset to all", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", type: "listing", title: "My Listing" }),
        mockItem({ id: "2", type: "agent", title: "My Agent" }),
      ],
    });

    const select = screen.getByDisplayValue("All Types");
    // Filter to listing
    fireEvent.change(select, { target: { value: "listing" } });
    expect(screen.queryByText("My Agent")).not.toBeInTheDocument();

    // Reset to all
    fireEvent.change(select, { target: { value: "all" } });
    expect(screen.getByText("My Listing")).toBeInTheDocument();
    expect(screen.getByText("My Agent")).toBeInTheDocument();
  });

  it("shows empty state when filter yields no results", () => {
    renderQueue({
      items: [mockItem({ id: "1", type: "listing", title: "Only Listing" })],
    });
    const select = screen.getByDisplayValue("All Types");
    fireEvent.change(select, { target: { value: "payout" } });
    expect(
      screen.getByText("No items in the moderation queue.")
    ).toBeInTheDocument();
  });

  it("can filter by content type", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", type: "content", title: "Content Item" }),
        mockItem({ id: "2", type: "payout", title: "Payout Item" }),
      ],
    });
    const select = screen.getByDisplayValue("All Types");
    fireEvent.change(select, { target: { value: "content" } });
    expect(screen.getByText("Content Item")).toBeInTheDocument();
    expect(screen.queryByText("Payout Item")).not.toBeInTheDocument();
  });

  it("can filter by payout type", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", type: "content", title: "Content Item" }),
        mockItem({ id: "2", type: "payout", title: "Payout Item" }),
      ],
    });
    const select = screen.getByDisplayValue("All Types");
    fireEvent.change(select, { target: { value: "payout" } });
    expect(screen.queryByText("Content Item")).not.toBeInTheDocument();
    expect(screen.getByText("Payout Item")).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Approve/Reject actions - only shown for pending items               */
  /* ------------------------------------------------------------------ */

  it("shows approve and reject buttons for pending items", () => {
    renderQueue({ items: [mockItem({ status: "pending" })] });
    expect(screen.getByTitle("Approve")).toBeInTheDocument();
    expect(screen.getByTitle("Reject")).toBeInTheDocument();
  });

  it("does not show approve/reject buttons for approved items", () => {
    renderQueue({ items: [mockItem({ status: "approved" })] });
    expect(screen.queryByTitle("Approve")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Reject")).not.toBeInTheDocument();
  });

  it("does not show approve/reject buttons for rejected items", () => {
    renderQueue({ items: [mockItem({ status: "rejected" })] });
    expect(screen.queryByTitle("Approve")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Reject")).not.toBeInTheDocument();
  });

  it("calls onApprove with the item id when Approve is clicked", () => {
    renderQueue({ items: [mockItem({ id: "test-approve-id" })] });
    fireEvent.click(screen.getByTitle("Approve"));
    expect(onApprove).toHaveBeenCalledWith("test-approve-id");
  });

  /* ------------------------------------------------------------------ */
  /* Reject flow                                                         */
  /* ------------------------------------------------------------------ */

  it("shows reject reason input when Reject button is clicked", () => {
    renderQueue({ items: [mockItem({ id: "rej-1" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    expect(
      screen.getByPlaceholderText("Reason for rejection...")
    ).toBeInTheDocument();
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("does not call onReject when confirm is clicked with empty reason", () => {
    renderQueue({ items: [mockItem({ id: "rej-2" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    // Click confirm without typing a reason
    fireEvent.click(screen.getByText("Confirm"));
    expect(onReject).not.toHaveBeenCalled();
  });

  it("does not call onReject when confirm is clicked with whitespace-only reason", () => {
    renderQueue({ items: [mockItem({ id: "rej-3" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(screen.getByText("Confirm"));
    expect(onReject).not.toHaveBeenCalled();
  });

  it("calls onReject with trimmed reason when confirm is clicked", () => {
    renderQueue({ items: [mockItem({ id: "rej-4" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "  Violates policy  " } });
    fireEvent.click(screen.getByText("Confirm"));
    expect(onReject).toHaveBeenCalledWith("rej-4", "Violates policy");
  });

  it("clears reject state after successful rejection", () => {
    renderQueue({ items: [mockItem({ id: "rej-5" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Bad content" } });
    fireEvent.click(screen.getByText("Confirm"));
    // After confirm, the reject input should disappear
    expect(
      screen.queryByPlaceholderText("Reason for rejection...")
    ).not.toBeInTheDocument();
  });

  it("closes reject input when Cancel button is clicked", () => {
    renderQueue({ items: [mockItem({ id: "rej-6" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    expect(
      screen.getByPlaceholderText("Reason for rejection...")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText("Cancel"));
    expect(
      screen.queryByPlaceholderText("Reason for rejection...")
    ).not.toBeInTheDocument();
  });

  it("submits rejection on Enter key press", () => {
    renderQueue({ items: [mockItem({ id: "rej-7" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Spam content" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onReject).toHaveBeenCalledWith("rej-7", "Spam content");
  });

  it("does not submit rejection on Enter with empty reason", () => {
    renderQueue({ items: [mockItem({ id: "rej-8" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onReject).not.toHaveBeenCalled();
  });

  it("closes reject input on Escape key press", () => {
    renderQueue({ items: [mockItem({ id: "rej-9" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Some reason" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(
      screen.queryByPlaceholderText("Reason for rejection...")
    ).not.toBeInTheDocument();
  });

  it("clears reject reason when Escape is pressed", () => {
    renderQueue({ items: [mockItem({ id: "rej-10" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Some reason" } });
    fireEvent.keyDown(input, { key: "Escape" });

    // Open reject again — input should be empty
    fireEvent.click(screen.getByTitle("Reject"));
    const newInput = screen.getByPlaceholderText("Reason for rejection...");
    expect((newInput as HTMLInputElement).value).toBe("");
  });

  it("disables confirm button when reason is empty", () => {
    renderQueue({ items: [mockItem({ id: "rej-11" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const confirmBtn = screen.getByText("Confirm");
    expect(confirmBtn).toBeDisabled();
  });

  it("enables confirm button when reason is provided", () => {
    renderQueue({ items: [mockItem({ id: "rej-12" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Valid reason" } });
    const confirmBtn = screen.getByText("Confirm");
    expect(confirmBtn).not.toBeDisabled();
  });

  /* ------------------------------------------------------------------ */
  /* Multiple items                                                      */
  /* ------------------------------------------------------------------ */

  it("renders multiple items", () => {
    renderQueue({
      items: [
        mockItem({ id: "1", title: "Item One" }),
        mockItem({ id: "2", title: "Item Two" }),
        mockItem({ id: "3", title: "Item Three" }),
      ],
    });
    expect(screen.getByText("Item One")).toBeInTheDocument();
    expect(screen.getByText("Item Two")).toBeInTheDocument();
    expect(screen.getByText("Item Three")).toBeInTheDocument();
  });

  it("renders with metadata without issues", () => {
    renderQueue({
      items: [mockItem({ metadata: { priority: "high" } })],
    });
    expect(screen.getByText("Test Listing")).toBeInTheDocument();
  });

  it("handles non-Enter and non-Escape key presses without side effects", () => {
    renderQueue({ items: [mockItem({ id: "key-1" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "test" } });
    // Press a random key that is not Enter or Escape
    fireEvent.keyDown(input, { key: "a" });
    // Should still be visible
    expect(
      screen.getByPlaceholderText("Reason for rejection...")
    ).toBeInTheDocument();
    expect(onReject).not.toHaveBeenCalled();
  });

  it("reject reason input updates as user types", () => {
    renderQueue({ items: [mockItem({ id: "type-1" })] });
    fireEvent.click(screen.getByTitle("Reject"));
    const input = screen.getByPlaceholderText(
      "Reason for rejection..."
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "First" } });
    expect(input.value).toBe("First");
    fireEvent.change(input, { target: { value: "First then second" } });
    expect(input.value).toBe("First then second");
  });
});

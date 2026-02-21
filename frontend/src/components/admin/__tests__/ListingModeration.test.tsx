import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ListingModeration from "../ListingModeration";
import type { PendingListing } from "../ListingModeration";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const makeListing = (overrides?: Partial<PendingListing>): PendingListing => ({
  id: "listing-1",
  seller_id: "seller-abcdef123456",
  seller_name: "Alice",
  title: "Premium Web Search Results",
  description: "High-quality web search data for training.",
  category: "web_search",
  price_usdc: 25,
  content_size: 2048,
  content_type: "application/json",
  quality_score: 0.92,
  tags: ["search", "web"],
  created_at: "2026-02-20T12:00:00Z",
  status: "pending",
  ...overrides,
});

const defaultProps = () => ({
  listings: [makeListing()],
  isLoading: false,
  onApprove: vi.fn(),
  onReject: vi.fn(),
  onViewContent: vi.fn(),
});

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("ListingModeration", () => {
  /* ---- Rendering listing items ---- */

  it("renders listing items for moderation", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    expect(screen.getByText("Premium Web Search Results")).toBeInTheDocument();
    expect(
      screen.getByText("High-quality web search data for training."),
    ).toBeInTheDocument();
    expect(screen.getByText("web search")).toBeInTheDocument(); // category
  });

  it("renders multiple listings", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Listing A" }),
      makeListing({ id: "2", title: "Listing B" }),
      makeListing({ id: "3", title: "Listing C" }),
    ];
    render(<ListingModeration {...props} />);

    expect(screen.getByText("Listing A")).toBeInTheDocument();
    expect(screen.getByText("Listing B")).toBeInTheDocument();
    expect(screen.getByText("Listing C")).toBeInTheDocument();
  });

  /* ---- Approve flow ---- */

  it("approve button triggers approve flow", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Approve"));
    expect(props.onApprove).toHaveBeenCalledWith("listing-1");
  });

  /* ---- Reject flow ---- */

  it("reject button opens reason input", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    expect(
      screen.getByPlaceholderText("Reason for rejection..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Confirm Reject")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("reason input appears on reject and accepts text", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Low quality content" } });

    expect(input).toHaveValue("Low quality content");
  });

  it("reason is required for rejection - empty reason does not call onReject", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    // Click confirm with empty reason
    fireEvent.click(screen.getByText("Confirm Reject"));

    expect(props.onReject).not.toHaveBeenCalled();
  });

  it("confirm reject button is disabled when reason is empty", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    const confirmBtn = screen.getByText("Confirm Reject");

    expect(confirmBtn).toBeDisabled();
  });

  it("reject calls onReject with reason when reason is provided", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Duplicate content" } });
    fireEvent.click(screen.getByText("Confirm Reject"));

    expect(props.onReject).toHaveBeenCalledWith("listing-1", "Duplicate content");
  });

  it("reject via Enter key calls onReject with reason", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Spam" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(props.onReject).toHaveBeenCalledWith("listing-1", "Spam");
  });

  it("Escape key cancels rejection and clears reason", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    const input = screen.getByPlaceholderText("Reason for rejection...");
    fireEvent.change(input, { target: { value: "Some reason" } });
    fireEvent.keyDown(input, { key: "Escape" });

    // The input should disappear after cancel
    expect(
      screen.queryByPlaceholderText("Reason for rejection..."),
    ).not.toBeInTheDocument();
  });

  it("cancel button closes rejection input", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Reject"));
    expect(
      screen.getByPlaceholderText("Reason for rejection..."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText("Cancel"));
    expect(
      screen.queryByPlaceholderText("Reason for rejection..."),
    ).not.toBeInTheDocument();
  });

  /* ---- Status tabs filter listings ---- */

  it("status tabs filter listings - pending tab (default)", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Pending Item", status: "pending" }),
      makeListing({ id: "2", title: "Approved Item", status: "approved" }),
      makeListing({ id: "3", title: "Rejected Item", status: "rejected" }),
    ];
    render(<ListingModeration {...props} />);

    // Default filter is "pending"
    expect(screen.getByText("Pending Item")).toBeInTheDocument();
    expect(screen.queryByText("Approved Item")).not.toBeInTheDocument();
    expect(screen.queryByText("Rejected Item")).not.toBeInTheDocument();
  });

  it("status tabs filter listings - approved tab", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Pending Item", status: "pending" }),
      makeListing({ id: "2", title: "Approved Item", status: "approved" }),
    ];
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("approved"));
    expect(screen.queryByText("Pending Item")).not.toBeInTheDocument();
    expect(screen.getByText("Approved Item")).toBeInTheDocument();
  });

  it("status tabs filter listings - rejected tab", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Pending Item", status: "pending" }),
      makeListing({ id: "2", title: "Rejected Item", status: "rejected" }),
    ];
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("rejected"));
    expect(screen.queryByText("Pending Item")).not.toBeInTheDocument();
    expect(screen.getByText("Rejected Item")).toBeInTheDocument();
  });

  it("status tabs filter listings - all tab shows everything", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Pending Item", status: "pending" }),
      makeListing({ id: "2", title: "Approved Item", status: "approved" }),
      makeListing({ id: "3", title: "Rejected Item", status: "rejected" }),
    ];
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("all"));
    expect(screen.getByText("Pending Item")).toBeInTheDocument();
    expect(screen.getByText("Approved Item")).toBeInTheDocument();
    expect(screen.getByText("Rejected Item")).toBeInTheDocument();
  });

  /* ---- Content preview ---- */

  it("content preview shows listing details when Preview is clicked", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    // Content Preview section should not be visible initially
    expect(screen.queryByText("Content Preview")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Preview"));

    expect(screen.getByText("Content Preview")).toBeInTheDocument();
    // The description is shown in the preview area
    expect(screen.getByText(/seller-abcde/)).toBeInTheDocument();
  });

  it("content preview toggles off when Preview is clicked again", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("Preview"));
    expect(screen.getByText("Content Preview")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Preview"));
    expect(screen.queryByText("Content Preview")).not.toBeInTheDocument();
  });

  /* ---- Loading state ---- */

  it("shows loading state with spinner", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} isLoading={true} />);

    expect(screen.getByText("Loading listings...")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
    // Should not show any listings
    expect(
      screen.queryByText("Premium Web Search Results"),
    ).not.toBeInTheDocument();
  });

  /* ---- Empty state ---- */

  it("shows empty state for pending tab when no pending listings", () => {
    const props = defaultProps();
    props.listings = [];
    render(<ListingModeration {...props} />);

    expect(
      screen.getByText("No listings pending approval."),
    ).toBeInTheDocument();
  });

  it("shows empty state for non-pending tab when filter has no matches", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Pending Item", status: "pending" }),
    ];
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("approved"));
    expect(
      screen.getByText("No listings match the selected filter."),
    ).toBeInTheDocument();
  });

  it("shows empty state for rejected tab when no rejected listings", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", title: "Pending Item", status: "pending" }),
    ];
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("rejected"));
    expect(
      screen.getByText("No listings match the selected filter."),
    ).toBeInTheDocument();
  });

  /* ---- Listing metadata display ---- */

  it("displays listing price, quality score, seller name, and date", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    // Price
    expect(screen.getByText("$25.00")).toBeInTheDocument();
    // Quality score
    expect(screen.getByText("92%")).toBeInTheDocument();
    // Seller name
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("displays tags for a listing", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    expect(screen.getByText("search")).toBeInTheDocument();
    expect(screen.getByText("web")).toBeInTheDocument();
  });

  it("does not display tags section when listing has no tags", () => {
    const props = defaultProps();
    props.listings = [makeListing({ tags: [] })];
    const { container } = render(<ListingModeration {...props} />);

    // No tag spans with rounded-full bg-[#1e293b] should be present
    const tagElements = container.querySelectorAll(".bg-\\[\\#1e293b\\]");
    expect(tagElements.length).toBe(0);
  });

  /* ---- Non-pending status badges ---- */

  it("shows status badge for approved listings instead of action buttons", () => {
    const props = defaultProps();
    props.listings = [makeListing({ status: "approved" })];
    render(<ListingModeration {...props} />);

    // "all" tab to see approved items
    fireEvent.click(screen.getByText("all"));
    // Should not have Approve/Reject buttons
    expect(screen.queryByText("Approve")).not.toBeInTheDocument();
    // Should show status badge (the text "approved" appears both in the tab and badge)
    // The badge is uppercase so let's check the status is displayed
    const badges = screen.getAllByText("approved");
    // At least one is the status badge (in addition to the tab button)
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });

  it("shows status badge for rejected listings instead of action buttons", () => {
    const props = defaultProps();
    props.listings = [makeListing({ status: "rejected" })];
    render(<ListingModeration {...props} />);

    fireEvent.click(screen.getByText("all"));
    expect(screen.queryByText("Approve")).not.toBeInTheDocument();
    const badges = screen.getAllByText("rejected");
    expect(badges.length).toBeGreaterThanOrEqual(2);
  });

  /* ---- onViewContent callback ---- */

  it("calls onViewContent when external link button is clicked", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    // The external link button has title "Open full content"
    const externalBtn = screen.getByTitle("Open full content");
    fireEvent.click(externalBtn);

    expect(props.onViewContent).toHaveBeenCalledWith("listing-1");
  });

  it("does not render external link button when onViewContent is not provided", () => {
    const props = defaultProps();
    render(
      <ListingModeration
        listings={props.listings}
        isLoading={props.isLoading}
        onApprove={props.onApprove}
        onReject={props.onReject}
      />,
    );

    expect(screen.queryByTitle("Open full content")).not.toBeInTheDocument();
  });

  /* ---- Pending count in header ---- */

  it("shows correct pending count in header", () => {
    const props = defaultProps();
    props.listings = [
      makeListing({ id: "1", status: "pending" }),
      makeListing({ id: "2", status: "pending" }),
      makeListing({ id: "3", status: "approved" }),
    ];
    render(<ListingModeration {...props} />);

    expect(screen.getByText("2 listings pending approval")).toBeInTheDocument();
  });

  it("shows singular pending count for one listing", () => {
    const props = defaultProps();
    props.listings = [makeListing({ id: "1", status: "pending" })];
    render(<ListingModeration {...props} />);

    expect(screen.getByText("1 listing pending approval")).toBeInTheDocument();
  });

  it("shows zero pending count", () => {
    const props = defaultProps();
    props.listings = [makeListing({ id: "1", status: "approved" })];
    render(<ListingModeration {...props} />);

    expect(
      screen.getByText("0 listings pending approval"),
    ).toBeInTheDocument();
  });

  /* ---- Header always present ---- */

  it("renders the Listing Moderation header", () => {
    const props = defaultProps();
    render(<ListingModeration {...props} />);

    expect(screen.getByText("Listing Moderation")).toBeInTheDocument();
  });
});

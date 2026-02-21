import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LiveEventFeed from "../LiveEventFeed";
import type { FeedEvent } from "../../../types/api";

function makeEvent(overrides: Partial<FeedEvent> = {}): FeedEvent {
  return {
    type: "listing_created",
    timestamp: new Date().toISOString(),
    data: { item: "Widget", price: 100 },
    ...overrides,
  };
}

describe("LiveEventFeed", () => {
  it("renders feed container with events", () => {
    const events = [makeEvent()];
    const { container } = render(<LiveEventFeed events={events} />);
    // The outer container uses space-y-3
    expect(container.querySelector(".space-y-3")).toBeInTheDocument();
  });

  it("displays events as they arrive", () => {
    const events = [
      makeEvent({ type: "listing_created" }),
      makeEvent({ type: "transaction_completed" }),
      makeEvent({ type: "express_purchase" }),
    ];
    render(<LiveEventFeed events={events} />);
    // The header shows the event count
    expect(screen.getByText(/Live Feed \(3 events\)/)).toBeInTheDocument();
    // Each event type badge is rendered (underscores replaced with spaces)
    expect(screen.getByText("listing created")).toBeInTheDocument();
    expect(screen.getByText("transaction completed")).toBeInTheDocument();
    expect(screen.getByText("express purchase")).toBeInTheDocument();
  });

  it("shows event type indicators (badge per type)", () => {
    const events = [
      makeEvent({ type: "demand_spike" }),
      makeEvent({ type: "leaderboard_change" }),
    ];
    render(<LiveEventFeed events={events} />);
    expect(screen.getByText("demand spike")).toBeInTheDocument();
    expect(screen.getByText("leaderboard change")).toBeInTheDocument();
  });

  it("shows timestamps for each event", () => {
    const events = [makeEvent()];
    const { container } = render(<LiveEventFeed events={events} />);
    // Each event row has a timestamp span (span.shrink-0 with font-mono)
    const timestampSpans = container.querySelectorAll("span.shrink-0");
    expect(timestampSpans.length).toBe(1);
    // Should contain a time-like string (digits and colons)
    expect(timestampSpans[0].textContent).toMatch(/\d{1,2}:\d{2}/);
  });

  it("renders the latest events at the bottom (natural order)", () => {
    const events = [
      makeEvent({ type: "listing_created" }),
      makeEvent({ type: "transaction_completed" }),
    ];
    const { container } = render(<LiveEventFeed events={events} />);
    const badges = container.querySelectorAll("span.inline-flex.items-center.rounded-md");
    expect(badges[0].textContent).toBe("listing created");
    expect(badges[1].textContent).toBe("transaction completed");
  });

  it("shows empty state when no events", () => {
    render(<LiveEventFeed events={[]} />);
    expect(
      screen.getByText("Listening for live events...")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Events from the marketplace WebSocket feed/)
    ).toBeInTheDocument();
  });

  it("handles different event types including unknown ones", () => {
    const events = [
      makeEvent({ type: "listing_created" }),
      makeEvent({ type: "express_purchase" }),
      makeEvent({ type: "unknown_custom_event" }),
    ];
    const { container } = render(<LiveEventFeed events={events} />);
    // All three events should render without crashing
    expect(screen.getByText("listing created")).toBeInTheDocument();
    expect(screen.getByText("express purchase")).toBeInTheDocument();
    expect(screen.getByText("unknown custom event")).toBeInTheDocument();
    // The event rows should all be present (3 items)
    const rows = container.querySelectorAll(".animate-slide-in");
    expect(rows.length).toBe(3);
  });
});

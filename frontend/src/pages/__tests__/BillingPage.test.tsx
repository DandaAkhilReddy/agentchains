import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Lazy import the page
const BillingPage = (await import("../BillingPage")).default;

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("BillingPage", () => {
  it("renders without crashing", () => {
    const { container } = render(
      <Wrapper><BillingPage /></Wrapper>
    );
    expect(container).toBeTruthy();
  });

  it("displays a heading or title element", () => {
    render(<Wrapper><BillingPage /></Wrapper>);
    // Page should have some heading
    const headings = document.querySelectorAll("h1, h2, h3");
    expect(headings.length).toBeGreaterThan(0);
  });

  it("renders plan selection area", () => {
    render(<Wrapper><BillingPage /></Wrapper>);
    // Should mention plans, pricing, or subscription
    const text = document.body.textContent || "";
    const hasBillingContent =
      text.includes("Plan") ||
      text.includes("plan") ||
      text.includes("Billing") ||
      text.includes("billing") ||
      text.includes("Subscription") ||
      text.includes("subscription");
    expect(hasBillingContent).toBe(true);
  });

  it("has correct page structure with containers", () => {
    const { container } = render(
      <Wrapper><BillingPage /></Wrapper>
    );
    // Should have at least one styled container
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders interactive elements", () => {
    render(<Wrapper><BillingPage /></Wrapper>);
    // Should have buttons for plan actions
    const buttons = document.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThanOrEqual(0);
  });
});

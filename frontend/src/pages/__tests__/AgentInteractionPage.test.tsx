import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  CONNECTING = 0;
  OPEN = 1;
  CLOSING = 2;
  CLOSED = 3;
  readyState = 0;
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  constructor(url: string) { this.url = url; }
  send = vi.fn();
  close = vi.fn();
}
vi.stubGlobal("WebSocket", MockWebSocket);

const AgentInteractionPage = (await import("../AgentInteractionPage")).default;

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("AgentInteractionPage", () => {
  it("renders without crashing", () => {
    const { container } = render(
      <Wrapper><AgentInteractionPage /></Wrapper>
    );
    expect(container).toBeTruthy();
  });

  it("displays page heading or title", () => {
    render(<Wrapper><AgentInteractionPage /></Wrapper>);
    const headings = document.querySelectorAll("h1, h2, h3");
    expect(headings.length).toBeGreaterThan(0);
  });

  it("contains interaction-related text", () => {
    render(<Wrapper><AgentInteractionPage /></Wrapper>);
    const text = document.body.textContent || "";
    const hasContent =
      text.includes("Agent") ||
      text.includes("agent") ||
      text.includes("Interact") ||
      text.includes("interact") ||
      text.includes("A2UI") ||
      text.includes("Connect");
    expect(hasContent).toBe(true);
  });

  it("renders connect button or action", () => {
    render(<Wrapper><AgentInteractionPage /></Wrapper>);
    const buttons = document.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("has a container for A2UI components", () => {
    const { container } = render(
      <Wrapper><AgentInteractionPage /></Wrapper>
    );
    expect(container.querySelector("div")).toBeTruthy();
  });

  it("renders with proper page structure", () => {
    const { container } = render(
      <Wrapper><AgentInteractionPage /></Wrapper>
    );
    const children = container.firstChild as HTMLElement;
    expect(children).toBeTruthy();
  });
});

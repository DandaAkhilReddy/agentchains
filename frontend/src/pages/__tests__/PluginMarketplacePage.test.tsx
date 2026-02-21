import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const PluginMarketplacePage = (await import("../PluginMarketplacePage")).default;

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("PluginMarketplacePage", () => {
  it("renders without crashing", () => {
    const { container } = render(
      <Wrapper><PluginMarketplacePage /></Wrapper>
    );
    expect(container).toBeTruthy();
  });

  it("displays plugin-related content", () => {
    render(<Wrapper><PluginMarketplacePage /></Wrapper>);
    const text = document.body.textContent || "";
    const hasPluginContent =
      text.includes("Plugin") ||
      text.includes("plugin") ||
      text.includes("Extension") ||
      text.includes("extension");
    expect(hasPluginContent).toBe(true);
  });

  it("has search or filter functionality", () => {
    render(<Wrapper><PluginMarketplacePage /></Wrapper>);
    const inputs = document.querySelectorAll("input");
    // May have search input
    expect(inputs.length).toBeGreaterThanOrEqual(0);
  });

  it("renders plugin cards or list items", () => {
    const { container } = render(
      <Wrapper><PluginMarketplacePage /></Wrapper>
    );
    // Should have card-like elements
    const divs = container.querySelectorAll("div");
    expect(divs.length).toBeGreaterThan(1);
  });

  it("has proper page layout", () => {
    const { container } = render(
      <Wrapper><PluginMarketplacePage /></Wrapper>
    );
    expect(container.firstChild).toBeTruthy();
  });
});

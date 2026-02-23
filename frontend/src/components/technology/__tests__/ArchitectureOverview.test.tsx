import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { renderWithProviders } from "../../../test/test-utils";
import ArchitectureOverview from "../ArchitectureOverview";

// Mock useSystemMetrics hook (uses react-query internally)
const mockSystemMetrics = vi.fn();

vi.mock("../../../hooks/useSystemMetrics", () => ({
  useSystemMetrics: () => mockSystemMetrics(),
}));

// Mock StatCard so we can verify props without deep rendering
vi.mock("../../StatCard", () => ({
  default: ({ label, value }: { label: string; value: string | number }) => (
    <div data-testid={`stat-${label}`}>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  ),
}));

describe("ArchitectureOverview", () => {
  const onNavigate = vi.fn();

  beforeEach(() => {
    onNavigate.mockClear();
    vi.useFakeTimers();
    mockSystemMetrics.mockReturnValue({
      data: {
        health: {
          agents_count: 42,
          listings_count: 128,
          transactions_count: 9500,
        },
        cdn: {
          overview: {
            total_requests: 1000,
            tier1_hits: 600,
            tier2_hits: 200,
            tier3_hits: 100,
          },
        },
      },
      isLoading: false,
      isError: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    // Clean up injected style tag
    const style = document.getElementById("arch-overview-keyframes");
    if (style) style.remove();
  });

  /* ------------------------------------------------------------------ */
  /* Basic rendering                                                     */
  /* ------------------------------------------------------------------ */

  it("renders the System Architecture heading", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByText("System Architecture")).toBeInTheDocument();
  });

  it("renders the subtitle with navigation hint", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(
      screen.getByText("Click any node to explore its subsystem")
    ).toBeInTheDocument();
  });

  it("renders all 4 layer labels (Clients, Core Platform, Intelligence, Data Layer)", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // Each label appears twice: once in the layer header, once in the bottom legend
    expect(screen.getAllByText("Clients").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Core Platform").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Intelligence").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Data Layer").length).toBeGreaterThanOrEqual(2);
  });

  it("renders all 14 architecture nodes", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // Layer 0 — Clients
    expect(screen.getByText("OpenClaw")).toBeInTheDocument();
    expect(screen.getByText("MCP Protocol")).toBeInTheDocument();
    expect(screen.getByText("REST API")).toBeInTheDocument();
    expect(screen.getByText("WebSocket")).toBeInTheDocument();
    // Layer 1 — Core
    expect(screen.getByText("FastAPI Gateway")).toBeInTheDocument();
    expect(screen.getByText("Smart Router")).toBeInTheDocument();
    expect(screen.getByText("ZKP Verifier")).toBeInTheDocument();
    expect(screen.getByText("3-Tier CDN")).toBeInTheDocument();
    expect(screen.getByText("Billing Engine")).toBeInTheDocument();
    // Layer 2 — Intelligence
    expect(screen.getByText("Demand Signals")).toBeInTheDocument();
    expect(screen.getByText("Price Oracle")).toBeInTheDocument();
    expect(screen.getByText("Reputation Engine")).toBeInTheDocument();
    // Layer 3 — Data
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("Content Store")).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Navigation clicks on various nodes                                  */
  /* ------------------------------------------------------------------ */

  it("calls onNavigate with 'router' when clicking Smart Router node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Smart Router"));
    expect(onNavigate).toHaveBeenCalledWith("router");
  });

  it("calls onNavigate with 'zkp' when clicking ZKP Verifier node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("ZKP Verifier"));
    expect(onNavigate).toHaveBeenCalledWith("zkp");
  });

  it("calls onNavigate with 'tokens' when clicking Billing Engine node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Billing Engine"));
    expect(onNavigate).toHaveBeenCalledWith("tokens");
  });

  it("calls onNavigate with 'router' when clicking FastAPI Gateway node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("FastAPI Gateway"));
    expect(onNavigate).toHaveBeenCalledWith("router");
  });

  it("calls onNavigate with 'cdn' when clicking 3-Tier CDN node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("3-Tier CDN"));
    expect(onNavigate).toHaveBeenCalledWith("cdn");
  });

  it("calls onNavigate with 'overview' when clicking OpenClaw node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("OpenClaw"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking MCP Protocol node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("MCP Protocol"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking REST API node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("REST API"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking WebSocket node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("WebSocket"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking Demand Signals node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Demand Signals"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking Price Oracle node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Price Oracle"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking Reputation Engine node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Reputation Engine"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking PostgreSQL node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("PostgreSQL"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  it("calls onNavigate with 'overview' when clicking Content Store node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Content Store"));
    expect(onNavigate).toHaveBeenCalledWith("overview");
  });

  /* ------------------------------------------------------------------ */
  /* StatCards with data                                                 */
  /* ------------------------------------------------------------------ */

  it("renders the 4 stat cards with correct metric values", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // StatCard mock renders label + value as text
    expect(screen.getByTestId("stat-Agents")).toHaveTextContent("42");
    expect(screen.getByTestId("stat-Listings")).toHaveTextContent("128");
    expect(screen.getByTestId("stat-Revenue")).toHaveTextContent("9500");
    // CDN Hit Rate = (600+200+100)/1000 * 100 = 90%
    expect(screen.getByTestId("stat-CDN Hit Rate")).toHaveTextContent("90%");
  });

  /* ------------------------------------------------------------------ */
  /* StatCards with null / missing data                                  */
  /* ------------------------------------------------------------------ */

  it("renders stat cards with 0 values when data is null", () => {
    mockSystemMetrics.mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    });
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByTestId("stat-Agents")).toHaveTextContent("0");
    expect(screen.getByTestId("stat-Listings")).toHaveTextContent("0");
    expect(screen.getByTestId("stat-Revenue")).toHaveTextContent("0");
    expect(screen.getByTestId("stat-CDN Hit Rate")).toHaveTextContent("0%");
  });

  it("renders 0% CDN hit rate when total_requests is 0", () => {
    mockSystemMetrics.mockReturnValue({
      data: {
        health: { agents_count: 1, listings_count: 2, transactions_count: 3 },
        cdn: {
          overview: {
            total_requests: 0,
            tier1_hits: 0,
            tier2_hits: 0,
            tier3_hits: 0,
          },
        },
      },
      isLoading: false,
      isError: false,
    });
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByTestId("stat-CDN Hit Rate")).toHaveTextContent("0%");
  });

  it("renders 0% CDN hit rate when cdn.overview is null", () => {
    mockSystemMetrics.mockReturnValue({
      data: {
        health: { agents_count: 5, listings_count: 10, transactions_count: 50 },
        cdn: { overview: null },
      },
      isLoading: false,
      isError: false,
    });
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByTestId("stat-CDN Hit Rate")).toHaveTextContent("0%");
  });

  /* ------------------------------------------------------------------ */
  /* Competitive Moat cards                                              */
  /* ------------------------------------------------------------------ */

  it("renders the 3 competitive moat cards", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByText("7 Routing Strategies")).toBeInTheDocument();
    expect(screen.getByText("Cryptographic Verification")).toBeInTheDocument();
    expect(screen.getByText("USD Billing")).toBeInTheDocument();
  });

  it("renders moat card descriptions", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(
      screen.getByText(/more strategies than any competitor/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/zero-knowledge proofs/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/2% platform fee/i)
    ).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Bottom legend                                                       */
  /* ------------------------------------------------------------------ */

  it("renders the bottom legend with layer colors and Data flow label", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // Legend repeats layer labels plus "Data flow"
    expect(screen.getByText("Data flow")).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Node descriptions                                                   */
  /* ------------------------------------------------------------------ */

  it("renders node description text for each node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByText("No Code")).toBeInTheDocument();
    expect(screen.getByText("Claude")).toBeInTheDocument();
    expect(screen.getByText("HTTP/JSON")).toBeInTheDocument();
    expect(screen.getByText("Real-time")).toBeInTheDocument();
    expect(screen.getByText("82 endpoints")).toBeInTheDocument();
    expect(screen.getByText("7 strategies")).toBeInTheDocument();
    expect(screen.getByText("4 proofs")).toBeInTheDocument();
    expect(screen.getByText("Cache layers")).toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Dynamic")).toBeInTheDocument();
    expect(screen.getByText("Trust scores")).toBeInTheDocument();
    expect(screen.getByText("Primary store")).toBeInTheDocument();
    expect(screen.getByText("HashFS")).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* NodeCard hover interactions                                         */
  /* ------------------------------------------------------------------ */

  it("handles hover on a node card - mouseEnter changes border and shadow", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    const nodeButton = screen.getByText("Smart Router").closest("button")!;
    expect(nodeButton).toBeDefined();

    fireEvent.mouseEnter(nodeButton);
    // After hover, border color should change to include the layer color
    expect(nodeButton.style.borderColor).not.toBe("rgba(255,255,255,0.06)");
    expect(nodeButton.style.boxShadow).not.toBe("none");
  });

  it("handles hover on a node card - mouseLeave resets border and shadow", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    const nodeButton = screen.getByText("Smart Router").closest("button")!;

    fireEvent.mouseEnter(nodeButton);
    fireEvent.mouseLeave(nodeButton);
    // JSDOM normalizes rgba values with spaces
    expect(nodeButton.style.borderColor).toMatch(/rgba\(255,\s*255,\s*255,\s*0\.06\)/);
    expect(nodeButton.style.boxShadow).toBe("none");
  });

  it("handles hover on different layer node cards", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);

    // Layer 0 node (purple)
    const openclawBtn = screen.getByText("OpenClaw").closest("button")!;
    fireEvent.mouseEnter(openclawBtn);
    expect(openclawBtn.style.boxShadow).toBeTruthy();
    fireEvent.mouseLeave(openclawBtn);
    expect(openclawBtn.style.boxShadow).toBe("none");

    // Layer 2 node (amber)
    const demandBtn = screen.getByText("Demand Signals").closest("button")!;
    fireEvent.mouseEnter(demandBtn);
    expect(demandBtn.style.boxShadow).toBeTruthy();
    fireEvent.mouseLeave(demandBtn);

    // Layer 3 node (green)
    const pgBtn = screen.getByText("PostgreSQL").closest("button")!;
    fireEvent.mouseEnter(pgBtn);
    expect(pgBtn.style.boxShadow).toBeTruthy();
    fireEvent.mouseLeave(pgBtn);
  });

  /* ------------------------------------------------------------------ */
  /* Competitive moat card hover interactions                            */
  /* ------------------------------------------------------------------ */

  it("handles hover on a competitive moat card - mouseEnter changes border", () => {
    const { container } = renderWithProviders(
      <ArchitectureOverview onNavigate={onNavigate} />
    );
    const moatCard = screen.getByText("7 Routing Strategies").closest("div.group")!;
    expect(moatCard).toBeDefined();

    fireEvent.mouseEnter(moatCard);
    expect(moatCard.style.boxShadow).toBeTruthy();
    expect(moatCard.style.boxShadow).not.toBe("none");
  });

  it("handles hover on a competitive moat card - mouseLeave resets styles", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    const moatCard = screen.getByText("7 Routing Strategies").closest("div.group")!;

    fireEvent.mouseEnter(moatCard);
    fireEvent.mouseLeave(moatCard);
    // JSDOM normalizes rgba values with spaces
    expect(moatCard.style.borderColor).toMatch(/rgba\(255,\s*255,\s*255,\s*0\.06\)/);
    expect(moatCard.style.boxShadow).toBe("none");
  });

  it("handles hover on each competitive moat card", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);

    const cards = [
      "7 Routing Strategies",
      "Cryptographic Verification",
      "USD Billing",
    ];

    for (const title of cards) {
      const card = screen.getByText(title).closest("div.group")!;
      fireEvent.mouseEnter(card);
      expect(card.style.boxShadow).toBeTruthy();
      fireEvent.mouseLeave(card);
      expect(card.style.boxShadow).toBe("none");
    }
  });

  /* ------------------------------------------------------------------ */
  /* Keyframes injection                                                 */
  /* ------------------------------------------------------------------ */

  it("injects keyframe styles into the document head on mount", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    const styleEl = document.getElementById("arch-overview-keyframes");
    expect(styleEl).toBeInTheDocument();
    expect(styleEl?.textContent).toContain("archFlowDash");
    expect(styleEl?.textContent).toContain("archFlowDot");
    expect(styleEl?.textContent).toContain("archNodeEnter");
    expect(styleEl?.textContent).toContain("archPulseGlow");
  });

  it("does not inject duplicate keyframe styles on re-render", () => {
    const { unmount } = renderWithProviders(
      <ArchitectureOverview onNavigate={onNavigate} />
    );
    // Render again -- should not duplicate
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    const styles = document.querySelectorAll("#arch-overview-keyframes");
    expect(styles.length).toBe(1);
    unmount();
  });

  /* ------------------------------------------------------------------ */
  /* Measurement and resize                                              */
  /* ------------------------------------------------------------------ */

  it("sets up a resize event listener and cleans it up on unmount", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");

    const { unmount } = renderWithProviders(
      <ArchitectureOverview onNavigate={onNavigate} />
    );

    expect(addSpy).toHaveBeenCalledWith("resize", expect.any(Function));

    unmount();
    expect(removeSpy).toHaveBeenCalledWith("resize", expect.any(Function));

    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("runs measurement after timeout delay", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // The measurement timer is set with setTimeout(measureNodes, 600)
    act(() => {
      vi.advanceTimersByTime(600);
    });
    // Should not throw or error
  });

  it("handles resize event by re-measuring nodes", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    act(() => {
      vi.advanceTimersByTime(600);
    });
    // Trigger resize
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });
    // Should not throw or error
  });

  /* ------------------------------------------------------------------ */
  /* SVG / Connections rendering                                         */
  /* ------------------------------------------------------------------ */

  it("renders the SVG container area for connections", () => {
    const { container } = renderWithProviders(
      <ArchitectureOverview onNavigate={onNavigate} />
    );
    // The diagram container div should exist
    const diagramArea = container.querySelector("div.relative");
    expect(diagramArea).toBeInTheDocument();
  });

  /* ------------------------------------------------------------------ */
  /* Node cards render with correct animation delays                     */
  /* ------------------------------------------------------------------ */

  it("renders node cards with staggered animation delays", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // First node in first layer should have delay 0*120 + 0*60 = 0
    const openclawBtn = screen.getByText("OpenClaw").closest("button")!;
    expect(openclawBtn.style.animation).toContain("0ms");

    // Second node in first layer should have delay 0*120 + 1*60 = 60
    const mcpBtn = screen.getByText("MCP Protocol").closest("button")!;
    expect(mcpBtn.style.animation).toContain("60ms");
  });

  /* ------------------------------------------------------------------ */
  /* Edge case: CDN hit rate calculation edge cases                      */
  /* ------------------------------------------------------------------ */

  it("computes 100% CDN hit rate correctly", () => {
    mockSystemMetrics.mockReturnValue({
      data: {
        health: { agents_count: 1, listings_count: 1, transactions_count: 1 },
        cdn: {
          overview: {
            total_requests: 500,
            tier1_hits: 300,
            tier2_hits: 150,
            tier3_hits: 50,
          },
        },
      },
      isLoading: false,
      isError: false,
    });
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByTestId("stat-CDN Hit Rate")).toHaveTextContent("100%");
  });
});

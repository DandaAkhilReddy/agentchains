import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../../test/test-utils";
import ArchitectureOverview from "../ArchitectureOverview";

// Mock useSystemMetrics hook (uses react-query internally)
vi.mock("../../../hooks/useSystemMetrics", () => ({
  useSystemMetrics: () => ({
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
  }),
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
  });

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

  it("renders the 4 stat cards with correct metric values", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // StatCard mock renders label + value as text
    expect(screen.getByTestId("stat-Agents")).toHaveTextContent("42");
    expect(screen.getByTestId("stat-Listings")).toHaveTextContent("128");
    expect(screen.getByTestId("stat-Revenue")).toHaveTextContent("9500");
    // CDN Hit Rate = (600+200+100)/1000 * 100 = 90%
    expect(screen.getByTestId("stat-CDN Hit Rate")).toHaveTextContent("90%");
  });

  it("renders the 3 competitive moat cards", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByText("7 Routing Strategies")).toBeInTheDocument();
    expect(screen.getByText("Cryptographic Verification")).toBeInTheDocument();
    expect(screen.getByText("USD Billing")).toBeInTheDocument();
  });

  it("renders the bottom legend with layer colors and Data flow label", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    // Legend repeats layer labels plus "Data flow"
    expect(screen.getByText("Data flow")).toBeInTheDocument();
  });

  it("renders node description text for each node", () => {
    renderWithProviders(<ArchitectureOverview onNavigate={onNavigate} />);
    expect(screen.getByText("No Code")).toBeInTheDocument();
    expect(screen.getByText("82 endpoints")).toBeInTheDocument();
    expect(screen.getByText("7 strategies")).toBeInTheDocument();
    expect(screen.getByText("4 proofs")).toBeInTheDocument();
    expect(screen.getByText("Cache layers")).toBeInTheDocument();
    expect(screen.getByText("Primary store")).toBeInTheDocument();
    expect(screen.getByText("HashFS")).toBeInTheDocument();
  });
});

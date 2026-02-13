import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import AgentsPage from "../AgentsPage";
import * as useAgentsHook from "../../hooks/useAgents";
import type { Agent, AgentListResponse } from "../../types/api";

// Mock the useAgents hook
vi.mock("../../hooks/useAgents");

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn(() => Promise.resolve()),
  },
});

const mockAgents: Agent[] = [
  {
    id: "agent-001-abcd-efgh",
    name: "Search Agent",
    description: "Web search specialist",
    agent_type: "seller",
    wallet_address: "0x1234",
    capabilities: ["web_search", "api_calls", "data_extraction", "nlp", "image_processing"],
    a2a_endpoint: "https://api.example.com/agent1",
    status: "active",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-02-01T00:00:00Z",
    last_seen_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(), // 2 minutes ago (online)
  },
  {
    id: "agent-002-ijkl-mnop",
    name: "Code Analyzer",
    description: "Code analysis specialist",
    agent_type: "buyer",
    wallet_address: "0x5678",
    capabilities: ["code_analysis", "documentation"],
    a2a_endpoint: "https://api.example.com/agent2",
    status: "inactive",
    created_at: "2025-01-15T00:00:00Z",
    updated_at: "2025-02-01T00:00:00Z",
    last_seen_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(), // 10 minutes ago (offline)
  },
  {
    id: "agent-003-qrst-uvwx",
    name: "Data Aggregator",
    description: "Multi-source data aggregator",
    agent_type: "both",
    wallet_address: "0x9abc",
    capabilities: ["aggregation", "filtering", "transformation"],
    a2a_endpoint: "https://api.example.com/agent3",
    status: "active",
    created_at: "2025-02-01T00:00:00Z",
    updated_at: "2025-02-01T00:00:00Z",
    last_seen_at: null, // Never seen
  },
];

const mockResponse: AgentListResponse = {
  total: 3,
  page: 1,
  page_size: 20,
  agents: mockAgents,
};

const mockResponseEmpty: AgentListResponse = {
  total: 0,
  page: 1,
  page_size: 20,
  agents: [],
};

const mockResponseLarge: AgentListResponse = {
  total: 45,
  page: 1,
  page_size: 20,
  agents: mockAgents,
};

describe("AgentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without crashing", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("All Types")).toBeInTheDocument();
  });

  it("shows loading skeleton when isLoading is true", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // Should show grid with skeleton cards
    // The SkeletonCard component should be present
    const grid = document.querySelector(".grid");
    expect(grid).toBeInTheDocument();
  });

  it("displays agent cards when data is loaded", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    expect(screen.getByText("Search Agent")).toBeInTheDocument();
    expect(screen.getByText("Code Analyzer")).toBeInTheDocument();
    expect(screen.getByText("Data Aggregator")).toBeInTheDocument();
    expect(screen.getByText("3 agents")).toBeInTheDocument();
  });

  it("shows empty state when no agents exist", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponseEmpty,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    expect(screen.getByText("No agents registered")).toBeInTheDocument();
  });

  it("renders type filter dropdown with correct options", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    const typeSelect = screen.getByDisplayValue("All Types");
    expect(typeSelect).toBeInTheDocument();

    // Check that all options exist
    const options = typeSelect.querySelectorAll("option");
    expect(options).toHaveLength(4); // All Types, Seller, Buyer, Both
    expect(options[0]).toHaveTextContent("All Types");
    expect(options[1]).toHaveTextContent("Seller");
    expect(options[2]).toHaveTextContent("Buyer");
    expect(options[3]).toHaveTextContent("Both");
  });

  it("renders status filter dropdown with correct options", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    const statusSelect = screen.getByDisplayValue("All Status");
    expect(statusSelect).toBeInTheDocument();

    // Check that all options exist
    const options = statusSelect.querySelectorAll("option");
    expect(options).toHaveLength(3); // All Status, Active, Inactive
    expect(options[0]).toHaveTextContent("All Status");
    expect(options[1]).toHaveTextContent("Active");
    expect(options[2]).toHaveTextContent("Inactive");
  });

  it("shows pagination when total exceeds 20 agents", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponseLarge,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeInTheDocument();
    expect(screen.getByText("45 agents")).toBeInTheDocument();
  });

  it("does not show pagination when total is 20 or less", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    expect(screen.queryByRole("button", { name: "Previous page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });

  it("shows online indicator for recently active agents", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // Search Agent was seen 2 minutes ago, should show online (pulsing dot)
    const onlineDots = document.querySelectorAll(".pulse-dot");
    expect(onlineDots.length).toBe(1);

    // Code Analyzer was seen 10 minutes ago, should be offline
    const offlineDots = document.querySelectorAll(".bg-text-muted");
    expect(offlineDots.length).toBeGreaterThan(0);
  });

  it("renders copy button for agent IDs", async () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    const copyButtons = screen.getAllByTitle("Copy to clipboard");
    expect(copyButtons.length).toBeGreaterThan(0);

    // Click first copy button
    fireEvent.click(copyButtons[0]);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("agent-001-abcd-efgh");
    });
  });

  it("updates type filter and resets page to 1", async () => {
    const mockUseAgents = vi.fn();
    mockUseAgents.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);
    vi.spyOn(useAgentsHook, "useAgents").mockImplementation(mockUseAgents);

    renderWithProviders(<AgentsPage />);

    // Initial call should have empty filters and page 1
    expect(mockUseAgents).toHaveBeenCalledWith({
      agent_type: undefined,
      status: undefined,
      page: 1,
    });

    // Change type filter
    const typeSelect = screen.getByDisplayValue("All Types");
    fireEvent.change(typeSelect, { target: { value: "seller" } });

    // Should trigger new query with seller type and reset page to 1
    await waitFor(() => {
      expect(mockUseAgents).toHaveBeenCalledWith({
        agent_type: "seller",
        status: undefined,
        page: 1,
      });
    });
  });

  it("updates status filter and resets page to 1", async () => {
    const mockUseAgents = vi.fn();
    mockUseAgents.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);
    vi.spyOn(useAgentsHook, "useAgents").mockImplementation(mockUseAgents);

    renderWithProviders(<AgentsPage />);

    // Change status filter
    const statusSelect = screen.getByDisplayValue("All Status");
    fireEvent.change(statusSelect, { target: { value: "active" } });

    // Should trigger new query with active status and reset page to 1
    await waitFor(() => {
      expect(mockUseAgents).toHaveBeenCalledWith({
        agent_type: undefined,
        status: "active",
        page: 1,
      });
    });
  });

  it("handles pagination next button click", async () => {
    const mockUseAgents = vi.fn();
    mockUseAgents.mockReturnValue({
      data: mockResponseLarge,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);
    vi.spyOn(useAgentsHook, "useAgents").mockImplementation(mockUseAgents);

    renderWithProviders(<AgentsPage />);

    const nextButton = screen.getByRole("button", { name: "Next page" });
    fireEvent.click(nextButton);

    // Should increment page
    await waitFor(() => {
      expect(mockUseAgents).toHaveBeenCalledWith({
        agent_type: undefined,
        status: undefined,
        page: 2,
      });
    });
  });

  it("handles pagination prev button click", async () => {
    const mockUseAgents = vi.fn();
    mockUseAgents.mockReturnValue({
      data: mockResponseLarge,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);
    vi.spyOn(useAgentsHook, "useAgents").mockImplementation(mockUseAgents);

    renderWithProviders(<AgentsPage />);

    // Click next to go to page 2
    const nextButton = screen.getByRole("button", { name: "Next page" });
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(mockUseAgents).toHaveBeenCalledWith({
        agent_type: undefined,
        status: undefined,
        page: 2,
      });
    });

    // Click prev to go back to page 1
    const prevButton = screen.getByRole("button", { name: "Previous page" });
    fireEvent.click(prevButton);

    await waitFor(() => {
      expect(mockUseAgents).toHaveBeenCalledWith({
        agent_type: undefined,
        status: undefined,
        page: 1,
      });
    });
  });

  it("disables prev button on first page", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponseLarge,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    const prevButton = screen.getByRole("button", { name: "Previous page" });
    expect(prevButton).toBeDisabled();
  });

  it("disables next button on last page", async () => {
    // Start with 21 agents on page 1 - pagination shows, next is enabled
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: { total: 21, page: 1, page_size: 20, agents: mockAgents },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // Click next to go to page 2
    const nextButton = screen.getByRole("button", { name: "Next page" });
    expect(nextButton).not.toBeDisabled(); // Should be enabled on page 1

    fireEvent.click(nextButton);

    // After clicking, component state changes to page 2
    // Wait for state update and check if next is now disabled
    // On page 2 with 21 total: 2 * 20 = 40 >= 21, so disabled
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    });
  });

  it("displays truncated agent IDs correctly", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // IDs longer than 8 chars should be truncated with "..."
    expect(screen.getAllByText("agent-00...")).toHaveLength(3);
  });

  it("displays agent capabilities with overflow indicator", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // Search Agent has 5 capabilities, should show first 4 plus "+1"
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.getByText("api_calls")).toBeInTheDocument();
    expect(screen.getByText("data_extraction")).toBeInTheDocument();
    expect(screen.getByText("nlp")).toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("displays correct relative time for last_seen_at", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // Search Agent (2m ago) should show "Seen just now" or "Seen 2m ago"
    expect(screen.getAllByText(/Seen (just now|[0-9]+m ago)/).length).toBeGreaterThan(0);

    // Data Aggregator (never seen) should show "Never seen"
    expect(screen.getByText("Never seen")).toBeInTheDocument();
  });

  it("displays agent type and status badges", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    expect(screen.getByText("seller")).toBeInTheDocument();
    expect(screen.getByText("buyer")).toBeInTheDocument();
    expect(screen.getByText("both")).toBeInTheDocument();
    expect(screen.getAllByText("active")).toHaveLength(2);
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("shows singular 'agent' for count of 1", () => {
    const singleAgentResponse: AgentListResponse = {
      total: 1,
      page: 1,
      page_size: 20,
      agents: [mockAgents[0]],
    };

    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: singleAgentResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    // Should say "1 agent" not "1 agents"
    expect(screen.getByText("1 agent")).toBeInTheDocument();
  });

  it("shows plural 'agents' for count other than 1", () => {
    vi.spyOn(useAgentsHook, "useAgents").mockReturnValue({
      data: mockResponse,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    renderWithProviders(<AgentsPage />);

    expect(screen.getByText("3 agents")).toBeInTheDocument();
  });
});

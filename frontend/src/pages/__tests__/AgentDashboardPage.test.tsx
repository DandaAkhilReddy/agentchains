import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "../../test/test-utils";
import AgentDashboardPage from "../AgentDashboardPage";
import * as authModule from "../../hooks/useAuth";
import * as api from "../../lib/api";

vi.mock("../../hooks/useAuth");
vi.mock("../../lib/api", () => ({
  fetchDashboardAgentMeV2: vi.fn(),
}));

describe("AgentDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows login panel when no agent token exists", () => {
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: null,
      login: vi.fn(),
      logout: vi.fn(),
    } as any);

    renderWithProviders(<AgentDashboardPage />);
    expect(screen.getByText("Agent Login")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In/i })).toBeInTheDocument();
  });

  it("loads and renders dashboard metrics for authenticated agent", async () => {
    const logout = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "agent-token",
      login: vi.fn(),
      logout,
    } as any);
    vi.mocked(api.fetchDashboardAgentMeV2).mockResolvedValue({
      agent_id: "agent-1",
      money_received_usd: 12.5,
      money_spent_usd: 2.1,
      info_used_count: 9,
      other_agents_served_count: 4,
      data_served_bytes: 2048,
      savings: {
        money_saved_for_others_usd: 7.75,
        fresh_cost_estimate_total_usd: 10.0,
      },
      trust_status: "verified",
      trust_tier: "T2",
      trust_score: 81,
      updated_at: new Date().toISOString(),
    } as any);

    renderWithProviders(<AgentDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Money Received")).toBeInTheDocument();
    });
    expect(screen.getByText("Info Used")).toBeInTheDocument();
    expect(screen.getByText("Other Agents Served")).toBeInTheDocument();
    expect(screen.getByText("Money Saved For Buyers")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Logout/i }));
    expect(logout).toHaveBeenCalled();
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import IntegrationsPage from "../IntegrationsPage";
import * as authModule from "../../hooks/useAuth";
import * as api from "../../lib/api";

vi.mock("../../hooks/useAuth");
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));
vi.mock("../../lib/api", () => ({
  registerOpenClawWebhook: vi.fn(),
  fetchOpenClawWebhooks: vi.fn(),
  deleteOpenClawWebhook: vi.fn(),
  testOpenClawWebhook: vi.fn(),
  fetchOpenClawStatus: vi.fn(),
}));

describe("IntegrationsPage", () => {
  const mockStatus = {
    connected: true,
    webhooks_count: 2,
    active_count: 1,
    last_delivery: "2026-02-20T10:00:00Z",
  };

  const mockWebhooks = {
    webhooks: [
      {
        id: "wh-1",
        gateway_url: "https://gateway.example.com/hook",
        event_types: ["opportunity", "transaction"],
        active: true,
        created_at: "2026-02-15T08:00:00Z",
      },
      {
        id: "wh-2",
        gateway_url: "https://other.example.com/webhook",
        event_types: ["demand_spike"],
        active: false,
        created_at: "2026-02-18T12:00:00Z",
      },
    ],
  };

  function mockAuthenticated() {
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "test-int-token",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    } as any);
  }

  function mockUnauthenticated() {
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);
  }

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock clipboard API
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    });
    vi.mocked(api.fetchOpenClawStatus).mockResolvedValue(mockStatus);
    vi.mocked(api.fetchOpenClawWebhooks).mockResolvedValue(mockWebhooks);
    vi.mocked(api.registerOpenClawWebhook).mockResolvedValue({ id: "wh-new" });
    vi.mocked(api.deleteOpenClawWebhook).mockResolvedValue({ message: "ok" });
    vi.mocked(api.testOpenClawWebhook).mockResolvedValue({
      success: true,
      message: "OK",
    });
  });

  it("shows auth gate when not authenticated", () => {
    mockUnauthenticated();
    renderWithProviders(<IntegrationsPage />);

    expect(screen.getByText("Connect Your Agent")).toBeInTheDocument();
    expect(
      screen.getByText("Paste your agent JWT to manage integrations"),
    ).toBeInTheDocument();
  });

  it("renders integrations page with title when authenticated", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Integrations")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Connect OpenClaw agents and webhooks"),
    ).toBeInTheDocument();
  });

  it("shows connection status indicator", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    expect(screen.getByText(/1\/2 active/)).toBeInTheDocument();
  });

  it("shows disconnected status when not connected", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawStatus).mockResolvedValue({
      connected: false,
      webhooks_count: 0,
      active_count: 0,
      last_delivery: null,
    });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
  });

  it("shows webhook registration form", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Connect OpenClaw")).toBeInTheDocument();
    });
    expect(screen.getByText("Gateway URL")).toBeInTheDocument();
    expect(screen.getByText("Bearer Token")).toBeInTheDocument();
    expect(screen.getByText("Event Types")).toBeInTheDocument();
  });

  it("shows available event types to select", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Opportunity")).toBeInTheDocument();
    });
    expect(screen.getByText("Demand Spike")).toBeInTheDocument();
    expect(screen.getByText("Transaction")).toBeInTheDocument();
    expect(screen.getByText("Listing Created")).toBeInTheDocument();
  });

  it("connect webhook button is disabled when form is incomplete", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Connect Webhook" }),
      ).toBeDisabled();
    });
  });

  it("registers webhook when form is filled and submitted", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Gateway URL")).toBeInTheDocument();
    });

    const urlInput = screen.getByPlaceholderText(
      "https://your-openclaw-gateway.example.com/webhook",
    );
    await user.type(urlInput, "https://my-gateway.com/hook");

    // Select an event type
    await user.click(screen.getByText("Opportunity"));

    const connectBtn = screen.getByRole("button", {
      name: "Connect Webhook",
    });
    expect(connectBtn).not.toBeDisabled();
    await user.click(connectBtn);

    await waitFor(() => {
      expect(api.registerOpenClawWebhook).toHaveBeenCalledWith(
        "test-int-token",
        expect.objectContaining({
          gateway_url: "https://my-gateway.com/hook",
          event_types: ["opportunity"],
        }),
      );
    });
  });

  it("shows registered webhooks table", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Registered Webhooks")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("https://other.example.com/webhook"),
    ).toBeInTheDocument();
  });

  it("shows empty webhooks state when none registered", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawWebhooks).mockResolvedValue({ webhooks: [] });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No webhooks registered yet"),
      ).toBeInTheDocument();
    });
  });

  it("shows quick setup section with install commands", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Quick Setup")).toBeInTheDocument();
    });
    expect(
      screen.getByText("clawhub install agentchains-marketplace"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("mcporter install agentchains-mcp"),
    ).toBeInTheDocument();
  });

  it("login flow works from auth gate", async () => {
    const loginFn = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: loginFn,
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);

    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    const input = screen.getByPlaceholderText("eyJhbGciOi...");
    await user.type(input, "my-integration-token");

    await user.click(screen.getByRole("button", { name: "Connect" }));

    expect(loginFn).toHaveBeenCalledWith("my-integration-token");
  });
});

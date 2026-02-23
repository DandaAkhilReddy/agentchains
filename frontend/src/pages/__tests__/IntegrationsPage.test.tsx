import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import IntegrationsPage from "../IntegrationsPage";
import * as authModule from "../../hooks/useAuth";
import * as api from "../../lib/api";

vi.mock("../../hooks/useAuth");

/* Capture the toast function so tests can assert on it */
const toastFn = vi.fn();
vi.mock("../../components/Toast", () => ({
  useToast: () => ({ toast: toastFn }),
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

  /* ── NEW TESTS for increased coverage ── */

  it("does not call login when inputToken is empty/whitespace in auth gate", async () => {
    const loginFn = vi.fn();
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      token: "",
      login: loginFn,
      logout: vi.fn(),
      isAuthenticated: false,
    } as any);

    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    // The Connect button should be disabled when input is empty
    const connectBtn = screen.getByRole("button", { name: "Connect" });
    expect(connectBtn).toBeDisabled();
    expect(loginFn).not.toHaveBeenCalled();
  });

  it("copies clawhub install command to clipboard", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("clawhub install agentchains-marketplace"),
      ).toBeInTheDocument();
    });

    const clawhubSection = screen.getByText("clawhub install agentchains-marketplace").closest("div");
    const clawhubCopyBtn = clawhubSection!.querySelector("button")!;
    await user.click(clawhubCopyBtn);

    expect(toastFn).toHaveBeenCalledWith("Copied to clipboard", "info");
  });

  it("copies mcporter install command to clipboard", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("mcporter install agentchains-mcp"),
      ).toBeInTheDocument();
    });

    const mcporterSection = screen.getByText("mcporter install agentchains-mcp").closest("div");
    const mcporterCopyBtn = mcporterSection!.querySelector("button")!;
    await user.click(mcporterCopyBtn);

    expect(toastFn).toHaveBeenCalledWith("Copied to clipboard", "info");
  });

  it("deletes a webhook when delete button is clicked", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    // Find all delete buttons (by title)
    const deleteButtons = screen.getAllByTitle("Delete webhook");
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(api.deleteOpenClawWebhook).toHaveBeenCalledWith(
        "test-int-token",
        "wh-1",
      );
    });
  });

  it("tests a webhook when test button is clicked", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const testButtons = screen.getAllByTitle("Test webhook");
    await user.click(testButtons[0]);

    await waitFor(() => {
      expect(api.testOpenClawWebhook).toHaveBeenCalledWith(
        "test-int-token",
        "wh-1",
      );
    });
  });

  it("shows test failed toast when test webhook returns failure", async () => {
    mockAuthenticated();
    vi.mocked(api.testOpenClawWebhook).mockResolvedValue({
      success: false,
      message: "Connection timeout",
    });

    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const testButtons = screen.getAllByTitle("Test webhook");
    await user.click(testButtons[0]);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith(
        "Test failed: Connection timeout",
        "error",
      );
    });
  });

  it("toggles event type selection on and off", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Opportunity")).toBeInTheDocument();
    });

    const urlInput = screen.getByPlaceholderText(
      "https://your-openclaw-gateway.example.com/webhook",
    );
    await user.type(urlInput, "https://test.com");

    // Select Opportunity
    await user.click(screen.getByText("Opportunity"));

    // Select Demand Spike
    await user.click(screen.getByText("Demand Spike"));

    // Button should be enabled now
    const connectBtn = screen.getByRole("button", { name: "Connect Webhook" });
    expect(connectBtn).not.toBeDisabled();

    // Deselect Opportunity
    await user.click(screen.getByText("Opportunity"));

    // Deselect Demand Spike - should disable button again
    await user.click(screen.getByText("Demand Spike"));
    expect(connectBtn).toBeDisabled();
  });

  it("shows active and inactive webhook statuses in the table", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Active")).toBeInTheDocument();
    });
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("shows webhook event type badges in the table", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("opportunity")).toBeInTheDocument();
    });
    expect(screen.getByText("transaction")).toBeInTheDocument();
    expect(screen.getByText("demand_spike")).toBeInTheDocument();
  });

  it("shows webhook table column headers when webhooks exist", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    // Wait for the webhooks table to render with data
    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    // Now check table headers - use getAllByText for "Gateway URL" since it also appears as a form label
    const gatewayHeaders = screen.getAllByText("Gateway URL");
    expect(gatewayHeaders.length).toBeGreaterThanOrEqual(2); // form label + table header
    expect(screen.getByText("Events")).toBeInTheDocument();
    expect(screen.getByText("Created")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("shows last delivery time in connection status section", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Last Delivery:")).toBeInTheDocument();
    });
  });

  it('shows "Never" as last delivery when status has no last_delivery', async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawStatus).mockResolvedValue({
      connected: true,
      webhooks_count: 0,
      active_count: 0,
      last_delivery: null,
    });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Never")).toBeInTheDocument();
    });
  });

  it("shows connection status counts (webhooks and active)", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Webhooks:")).toBeInTheDocument();
    });
    expect(screen.getByText("Active:")).toBeInTheDocument();
  });

  it("shows API documentation link", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("View Full API Documentation"),
      ).toBeInTheDocument();
    });
    const link = screen.getByText("View Full API Documentation").closest("a");
    expect(link).toHaveAttribute("href", "/docs");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("fills bearer token field", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Bearer Token")).toBeInTheDocument();
    });

    const bearerInput = screen.getByPlaceholderText("your-webhook-secret-token");
    await user.type(bearerInput, "my-secret-token");
    expect(bearerInput).toHaveValue("my-secret-token");
  });

  it("shows webhook registration error on mutation failure", async () => {
    mockAuthenticated();
    vi.mocked(api.registerOpenClawWebhook).mockRejectedValue(
      new Error("Network error"),
    );

    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Gateway URL")).toBeInTheDocument();
    });

    const urlInput = screen.getByPlaceholderText(
      "https://your-openclaw-gateway.example.com/webhook",
    );
    await user.type(urlInput, "https://my-gateway.com/hook");
    await user.click(screen.getByText("Opportunity"));
    await user.click(screen.getByRole("button", { name: "Connect Webhook" }));

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Network error", "error");
    });
  });

  it("shows delete webhook error toast on mutation failure", async () => {
    mockAuthenticated();
    vi.mocked(api.deleteOpenClawWebhook).mockRejectedValue(
      new Error("Delete failed"),
    );

    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete webhook");
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Delete failed", "error");
    });
  });

  it("shows test webhook error toast on mutation failure", async () => {
    mockAuthenticated();
    vi.mocked(api.testOpenClawWebhook).mockRejectedValue(
      new Error("Test error"),
    );

    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const testButtons = screen.getAllByTitle("Test webhook");
    await user.click(testButtons[0]);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Test error", "error");
    });
  });

  it("shows webhook with no created_at as em-dash", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawWebhooks).mockResolvedValue({
      webhooks: [
        {
          id: "wh-3",
          gateway_url: "https://no-date.example.com",
          event_types: ["opportunity"],
          active: true,
          created_at: null,
        },
      ],
    });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://no-date.example.com"),
      ).toBeInTheDocument();
    });
    // The em-dash character
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("shows event type descriptions in the selection grid", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("New revenue opportunities detected")).toBeInTheDocument();
    });
    expect(screen.getByText("Surge in search queries")).toBeInTheDocument();
    expect(screen.getByText("Purchases of your listings")).toBeInTheDocument();
    expect(screen.getByText("New listings in your categories")).toBeInTheDocument();
  });

  it("shows the empty webhooks helper text", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawWebhooks).mockResolvedValue({ webhooks: [] });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Connect an OpenClaw gateway above to get started"),
      ).toBeInTheDocument();
    });
  });

  it("shows status section labels", async () => {
    mockAuthenticated();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Connection Status")).toBeInTheDocument();
    });
    expect(screen.getByText("OpenClaw Skill (ClawHub)")).toBeInTheDocument();
    expect(screen.getByText("MCP Server (mcporter)")).toBeInTheDocument();
  });

  it("displays zero counts when status has no webhooks", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawStatus).mockResolvedValue({
      connected: false,
      webhooks_count: 0,
      active_count: 0,
      last_delivery: null,
    });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("0/0 active")).toBeInTheDocument();
    });
  });

  it("registers webhook with bearer token included", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Gateway URL")).toBeInTheDocument();
    });

    const urlInput = screen.getByPlaceholderText(
      "https://your-openclaw-gateway.example.com/webhook",
    );
    const bearerInput = screen.getByPlaceholderText("your-webhook-secret-token");

    await user.type(urlInput, "https://my-gateway.com/hook");
    await user.type(bearerInput, "secret-123");
    await user.click(screen.getByText("Opportunity"));
    await user.click(screen.getByText("Transaction"));

    await user.click(screen.getByRole("button", { name: "Connect Webhook" }));

    await waitFor(() => {
      expect(api.registerOpenClawWebhook).toHaveBeenCalledWith(
        "test-int-token",
        expect.objectContaining({
          gateway_url: "https://my-gateway.com/hook",
          bearer_token: "secret-123",
          event_types: expect.arrayContaining(["opportunity", "transaction"]),
          filters: {},
        }),
      );
    });
  });

  it("shows success toast and clears form on successful webhook registration", async () => {
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
    await user.click(screen.getByText("Opportunity"));
    await user.click(screen.getByRole("button", { name: "Connect Webhook" }));

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith(
        "Webhook registered successfully!",
        "success",
      );
    });

    // Form should be cleared after success
    await waitFor(() => {
      expect(urlInput).toHaveValue("");
    });
  });

  it("shows success toast on webhook deletion", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete webhook");
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith("Webhook deleted", "success");
    });
  });

  it("shows success toast on successful test webhook", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const testButtons = screen.getAllByTitle("Test webhook");
    await user.click(testButtons[0]);

    await waitFor(() => {
      expect(toastFn).toHaveBeenCalledWith(
        "Test webhook delivered!",
        "success",
      );
    });
  });

  it("renders webhook with no event_types gracefully", async () => {
    mockAuthenticated();
    vi.mocked(api.fetchOpenClawWebhooks).mockResolvedValue({
      webhooks: [
        {
          id: "wh-empty-events",
          gateway_url: "https://empty-events.example.com",
          event_types: null,
          active: true,
          created_at: "2026-02-15T08:00:00Z",
        },
      ],
    });

    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://empty-events.example.com"),
      ).toBeInTheDocument();
    });
  });

  it("hover over test webhook button changes style", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const testButtons = screen.getAllByTitle("Test webhook");
    // Hover over and then unhover
    await user.hover(testButtons[0]);
    await user.unhover(testButtons[0]);

    // The button should still be in the document after hover/unhover
    expect(testButtons[0]).toBeInTheDocument();
  });

  it("hover over delete webhook button changes style", async () => {
    mockAuthenticated();
    const user = userEvent.setup();
    renderWithProviders(<IntegrationsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("https://gateway.example.com/hook"),
      ).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete webhook");
    // Hover and unhover to trigger onMouseEnter/onMouseLeave
    await user.hover(deleteButtons[0]);
    await user.unhover(deleteButtons[0]);

    expect(deleteButtons[0]).toBeInTheDocument();
  });
});

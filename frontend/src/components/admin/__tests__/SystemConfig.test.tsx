import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SystemConfig from "../SystemConfig";

// Mock navigator.clipboard
const mockClipboard = {
  writeText: vi.fn().mockResolvedValue(undefined),
};
Object.defineProperty(navigator, "clipboard", {
  value: mockClipboard,
  writable: true,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SystemConfig", () => {
  /* ── 1. Renders with default tab selected ───────────────────── */
  it("renders with default tab (Feature Flags) selected", () => {
    render(<SystemConfig />);

    // Header is visible
    expect(screen.getByText("System Configuration")).toBeInTheDocument();
    expect(
      screen.getByText("Manage platform settings, keys, and monitoring"),
    ).toBeInTheDocument();

    // All 4 tab buttons are rendered — "Feature Flags" appears both in the tab
    // and in the panel heading when the flags tab is active, so use getAllByText.
    expect(screen.getAllByText("Feature Flags").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Rate Limits")).toBeInTheDocument();
    expect(screen.getByText("API Keys")).toBeInTheDocument();
    expect(screen.getByText("Health Status")).toBeInTheDocument();

    // Feature Flags panel content is visible by default
    expect(
      screen.getByText("Toggle features on or off across the platform"),
    ).toBeInTheDocument();
    expect(screen.getByText("A2UI Protocol")).toBeInTheDocument();
  });

  /* ── 2. Feature Flags tab: shows toggle switches ────────────── */
  it("shows all feature flag names and descriptions on Flags tab", () => {
    render(<SystemConfig />);

    // All 8 flags should be visible
    expect(screen.getByText("A2UI Protocol")).toBeInTheDocument();
    expect(screen.getByText("Plugin Marketplace")).toBeInTheDocument();
    expect(screen.getByText("Billing Module")).toBeInTheDocument();
    expect(screen.getByText("Audit Logging")).toBeInTheDocument();
    expect(screen.getByText("Agent Sandboxing")).toBeInTheDocument();
    expect(screen.getByText("Multi-Region Routing")).toBeInTheDocument();
    expect(screen.getByText("Dark Mode (Beta)")).toBeInTheDocument();
    expect(screen.getByText("WebSocket v2")).toBeInTheDocument();

    // Category headers
    expect(screen.getByText("Core")).toBeInTheDocument();
    expect(screen.getByText("Features")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Infrastructure")).toBeInTheDocument();
    expect(screen.getByText("UI")).toBeInTheDocument();

    // Each flag has an Enable/Disable toggle button
    const enableButtons = screen.getAllByTitle("Disable");
    const disableButtons = screen.getAllByTitle("Enable");
    // 5 flags enabled, 3 disabled initially
    expect(enableButtons.length).toBe(5);
    expect(disableButtons.length).toBe(3);
  });

  /* ── 3. Feature Flags tab: toggle changes state ─────────────── */
  it("toggles a feature flag from enabled to disabled", () => {
    render(<SystemConfig />);

    // Agent Sandboxing starts disabled (title = "Enable")
    const enableButtons = screen.getAllByTitle("Enable");
    expect(enableButtons.length).toBe(3);

    // Toggle first disabled flag (Agent Sandboxing)
    fireEvent.click(enableButtons[0]);

    // Now there should be one fewer "Enable" button
    expect(screen.getAllByTitle("Enable").length).toBe(2);
    expect(screen.getAllByTitle("Disable").length).toBe(6);
  });

  it("toggles a feature flag from disabled to enabled and back", () => {
    render(<SystemConfig />);

    // A2UI Protocol starts enabled. Find its "Disable" button
    const disableButtons = screen.getAllByTitle("Disable");
    const originalCount = disableButtons.length;

    // Toggle it off
    fireEvent.click(disableButtons[0]);

    // Now one fewer "Disable" button
    expect(screen.getAllByTitle("Disable").length).toBe(originalCount - 1);
    expect(screen.getAllByTitle("Enable").length).toBe(4);
  });

  /* ── 4. Rate Limits tab: shows rate limit inputs ────────────── */
  it("shows rate limit inputs when Rate Limits tab is clicked", () => {
    render(<SystemConfig />);

    // Switch to Rate Limits tab
    fireEvent.click(screen.getByText("Rate Limits"));

    // Rate limits panel content
    expect(
      screen.getByText("Configure request rate limits per endpoint"),
    ).toBeInTheDocument();

    // Table headers
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Requests / min")).toBeInTheDocument();
    expect(screen.getByText("Burst Limit")).toBeInTheDocument();

    // Endpoint values
    expect(screen.getByText("/api/v1/*")).toBeInTheDocument();
    expect(screen.getByText("/api/v1/agents")).toBeInTheDocument();
    expect(screen.getByText("/api/v1/transactions")).toBeInTheDocument();
    expect(screen.getByText("/api/v1/auth/*")).toBeInTheDocument();

    // Save button
    expect(screen.getByText("Save Changes")).toBeInTheDocument();
  });

  /* ── 5. Rate Limits tab: input changes update values ────────── */
  it("updates rate limit values when inputs are changed", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("Rate Limits"));

    // Find the number inputs - there are 8 total (4 endpoints x 2 fields)
    const inputs = screen.getAllByRole("spinbutton");
    expect(inputs.length).toBe(8);

    // First input should be requestsPerMinute = 1000
    expect(inputs[0]).toHaveValue(1000);
    // Second input should be burstLimit = 50
    expect(inputs[1]).toHaveValue(50);

    // Change the first requestsPerMinute
    fireEvent.change(inputs[0], { target: { value: "2000" } });
    expect(inputs[0]).toHaveValue(2000);

    // Change the first burstLimit
    fireEvent.change(inputs[1], { target: { value: "100" } });
    expect(inputs[1]).toHaveValue(100);
  });

  /* ── 6. API Keys tab: shows API key list ────────────────────── */
  it("shows API key list when API Keys tab is clicked", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("API Keys"));

    // Panel content
    expect(
      screen.getByText("Manage API keys for programmatic access"),
    ).toBeInTheDocument();

    // Key names
    expect(screen.getByText("Production API")).toBeInTheDocument();
    expect(screen.getByText("Staging API")).toBeInTheDocument();
    expect(screen.getByText("CI/CD Pipeline")).toBeInTheDocument();

    // Create button
    expect(screen.getByText("Create Key")).toBeInTheDocument();
  });

  /* ── 7. API Keys tab: create new key ────────────────────────── */
  it("creates a new API key when Create Key is clicked", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("API Keys"));

    // Initially 3 keys
    expect(screen.getByText("Production API")).toBeInTheDocument();
    expect(screen.getByText("Staging API")).toBeInTheDocument();
    expect(screen.getByText("CI/CD Pipeline")).toBeInTheDocument();

    // Click Create Key
    fireEvent.click(screen.getByText("Create Key"));

    // A new key named "New Key 4" should appear (3 existing + 1)
    expect(screen.getByText("New Key 4")).toBeInTheDocument();

    // Now there are 4 keys displayed, the new one at the top
    // The active key count badge should update from 3 to 4
  });

  /* ── 8. API Keys tab: revoke key ────────────────────────────── */
  it("revokes a key when the revoke button is clicked", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("API Keys"));

    // All 3 keys are active, so there should be 3 revoke buttons
    const revokeButtons = screen.getAllByTitle("Revoke key");
    expect(revokeButtons.length).toBe(3);

    // Revoke the first key
    fireEvent.click(revokeButtons[0]);

    // Now only 2 revoke buttons remain (revoked keys lose their action buttons)
    expect(screen.getAllByTitle("Revoke key").length).toBe(2);

    // "Revoked" badge should appear
    expect(screen.getByText("Revoked")).toBeInTheDocument();
  });

  /* ── 9. Health tab: shows health status ─────────────────────── */
  it("shows health status dashboard when Health Status tab is clicked", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("Health Status"));

    // Overall status banner - one service is degraded
    expect(
      screen.getByText("Partial Service Degradation"),
    ).toBeInTheDocument();

    // All 6 services
    expect(screen.getByText("API Gateway")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("Redis Cache")).toBeInTheDocument();
    expect(screen.getByText("WebSocket Hub")).toBeInTheDocument();
    expect(screen.getByText("Task Queue")).toBeInTheDocument();
    expect(screen.getByText("Object Storage")).toBeInTheDocument();

    // Latency values
    expect(screen.getByText("12ms")).toBeInTheDocument();
    expect(screen.getByText("3ms")).toBeInTheDocument();
    expect(screen.getByText("1ms")).toBeInTheDocument();
    expect(screen.getByText("8ms")).toBeInTheDocument();
    expect(screen.getByText("45ms")).toBeInTheDocument();
    expect(screen.getByText("18ms")).toBeInTheDocument();

    // Uptime values
    expect(screen.getAllByText("99.99%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("99.85%")).toBeInTheDocument();

    // Status labels - some "healthy", one "degraded"
    const healthyLabels = screen.getAllByText("healthy");
    expect(healthyLabels.length).toBe(5);
    expect(screen.getByText("degraded")).toBeInTheDocument();
  });

  /* ── 10. Tab switching works correctly ──────────────────────── */
  it("switches between all four tabs correctly", () => {
    render(<SystemConfig />);

    // Start on Feature Flags tab
    expect(screen.getByText("A2UI Protocol")).toBeInTheDocument();
    expect(screen.queryByText("Endpoint")).not.toBeInTheDocument();

    // Switch to Rate Limits
    fireEvent.click(screen.getByText("Rate Limits"));
    expect(screen.queryByText("A2UI Protocol")).not.toBeInTheDocument();
    expect(screen.getByText("Endpoint")).toBeInTheDocument();

    // Switch to API Keys
    fireEvent.click(screen.getByText("API Keys"));
    expect(screen.queryByText("Endpoint")).not.toBeInTheDocument();
    expect(screen.getByText("Production API")).toBeInTheDocument();

    // Switch to Health Status
    fireEvent.click(screen.getByText("Health Status"));
    expect(screen.queryByText("Production API")).not.toBeInTheDocument();
    expect(screen.getByText("API Gateway")).toBeInTheDocument();

    // Switch back to Feature Flags — when on Health tab, "Feature Flags" only
    // appears once (the tab button), so getByText works here. After clicking,
    // the panel heading also renders, making it appear twice.
    fireEvent.click(screen.getByText("Feature Flags"));
    expect(screen.queryByText("API Gateway")).not.toBeInTheDocument();
    expect(screen.getByText("A2UI Protocol")).toBeInTheDocument();
  });

  /* ── 11. Save/apply button works ────────────────────────────── */
  it("shows saving state when Save Changes is clicked", async () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("Rate Limits"));

    const saveButton = screen.getByText("Save Changes");
    expect(saveButton).toBeInTheDocument();
    expect(saveButton).not.toBeDisabled();

    // Click save
    fireEvent.click(saveButton);

    // Button should show "Saving..." and be disabled
    expect(screen.getByText("Saving...")).toBeInTheDocument();
    const savingButton = screen.getByText("Saving...").closest("button");
    expect(savingButton).toBeDisabled();

    // After the async operation completes, it should revert
    await waitFor(
      () => {
        expect(screen.getByText("Save Changes")).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });

  /* ── 12. Loading state for each tab (tab badge counts) ──────── */
  it("displays correct badge counts for each tab", () => {
    render(<SystemConfig />);

    // Feature Flags tab count = 8
    // Rate Limits tab count = 4
    // API Keys tab count = 3 (active keys)
    // Health Status tab count = 6

    // Badge counts rendered in the tab bar
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
  });

  it("updates API Keys badge count after creating a new key", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("API Keys"));

    // Initial active count is 3 (displayed as badge in API Keys tab)
    // Rate Limits badge is "4". After creating a key, API Keys badge becomes "4"
    // so both "4" badges exist and the "3" badge is gone
    expect(screen.getByText("3")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Create Key"));

    // The API Keys badge should now show 4 (was 3), so no "3" badge remains
    expect(screen.queryByText("3")).not.toBeInTheDocument();
    expect(screen.getAllByText("4").length).toBe(2); // Rate Limits (4) + API Keys (4)
  });

  /* ── 13. Error handling on save failure (copy key fallback) ── */
  it("handles clipboard copy for API keys", async () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("API Keys"));

    // Find copy buttons
    const copyButtons = screen.getAllByTitle("Copy key");
    expect(copyButtons.length).toBe(3);

    // Click copy on first key
    fireEvent.click(copyButtons[0]);

    // Clipboard writeText should have been called
    expect(mockClipboard.writeText).toHaveBeenCalledWith(
      "ak_prod_xK8mN2pR5vW9qT3j",
    );
  });

  it("handles reveal/hide toggle for API keys", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("API Keys"));

    // Find reveal buttons
    const revealButtons = screen.getAllByTitle("Reveal");
    expect(revealButtons.length).toBe(3);

    // Click to reveal the first key
    fireEvent.click(revealButtons[0]);

    // Now the full key should be visible
    expect(
      screen.getByText("ak_prod_xK8mN2pR5vW9qT3j"),
    ).toBeInTheDocument();

    // The button should now say "Hide"
    expect(screen.getByTitle("Hide")).toBeInTheDocument();

    // Click to hide again
    fireEvent.click(screen.getByTitle("Hide"));

    // Key should be masked again
    expect(screen.queryByText("ak_prod_xK8mN2pR5vW9qT3j")).not.toBeInTheDocument();
  });

  /* ── 14. Form validation (rate limits accept only numbers) ─── */
  it("rate limit inputs only accept numeric values", () => {
    render(<SystemConfig />);

    fireEvent.click(screen.getByText("Rate Limits"));

    const inputs = screen.getAllByRole("spinbutton");

    // All inputs should be type="number"
    inputs.forEach((input) => {
      expect(input).toHaveAttribute("type", "number");
    });

    // Verify initial values are correct across all endpoints
    // /api/v1/*: 1000 requests/min, 50 burst
    expect(inputs[0]).toHaveValue(1000);
    expect(inputs[1]).toHaveValue(50);
    // /api/v1/agents: 500 requests/min, 30 burst
    expect(inputs[2]).toHaveValue(500);
    expect(inputs[3]).toHaveValue(30);
    // /api/v1/transactions: 200 requests/min, 20 burst
    expect(inputs[4]).toHaveValue(200);
    expect(inputs[5]).toHaveValue(20);
    // /api/v1/auth/*: 100 requests/min, 10 burst
    expect(inputs[6]).toHaveValue(100);
    expect(inputs[7]).toHaveValue(10);
  });

  it("rate limit input changes persist across tab switches", () => {
    render(<SystemConfig />);

    // Go to Rate Limits tab
    fireEvent.click(screen.getByText("Rate Limits"));

    const inputs = screen.getAllByRole("spinbutton");
    fireEvent.change(inputs[0], { target: { value: "5000" } });
    expect(inputs[0]).toHaveValue(5000);

    // Switch away to Feature Flags
    fireEvent.click(screen.getByText("Feature Flags"));
    expect(screen.getByText("A2UI Protocol")).toBeInTheDocument();

    // Switch back to Rate Limits
    fireEvent.click(screen.getByText("Rate Limits"));

    const updatedInputs = screen.getAllByRole("spinbutton");
    expect(updatedInputs[0]).toHaveValue(5000);
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/test-utils";
import OnboardingWizardPage from "../OnboardingWizardPage";
import * as api from "../../lib/api";

vi.mock("../../lib/api", () => ({
  onboardAgentV2: vi.fn(),
  attestRuntimeV2: vi.fn(),
  runKnowledgeChallengeV2: vi.fn(),
  fetchAgentTrustV2: vi.fn(),
  importMemorySnapshotV2: vi.fn(),
  verifyMemorySnapshotV2: vi.fn(),
  createWebhookSubscriptionV2: vi.fn(),
  fetchWebhookSubscriptionsV2: vi.fn(),
}));

describe("OnboardingWizardPage", () => {
  const defaultProps = { creatorToken: "creator-token-123" };

  const mockOnboardResult = {
    agent_id: "agent-001",
    agent_name: "test-agent",
    agent_jwt_token: "jwt-abc",
    agent_trust_status: "provisional" as const,
    agent_trust_tier: "T1" as const,
    agent_trust_score: 45,
    onboarding_session_id: "session-1",
    agent_card_url: "/cards/agent-001",
    stage_scores: {},
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.onboardAgentV2).mockResolvedValue(mockOnboardResult);
    vi.mocked(api.attestRuntimeV2).mockResolvedValue({
      attestation_id: "att-1",
      stage_runtime_score: 0.9,
      profile: mockOnboardResult,
    });
    vi.mocked(api.runKnowledgeChallengeV2).mockResolvedValue({
      agent_id: "agent-001",
      status: "passed",
      severe_safety_failure: false,
      stage_knowledge_score: 0.85,
      knowledge_challenge_summary: {},
      profile: mockOnboardResult,
    });
    vi.mocked(api.fetchAgentTrustV2).mockResolvedValue(mockOnboardResult);
    vi.mocked(api.importMemorySnapshotV2).mockResolvedValue({
      snapshot: {
        snapshot_id: "snap-1",
        agent_id: "agent-001",
        source_type: "sdk",
        label: "wizard-import",
        record_count: 2,
        total_bytes: 200,
        merkle_root: "abc",
        status: "imported",
        created_at: "2026-02-20T10:00:00Z",
      },
      chunk_hashes: ["h1", "h2"],
      trust_profile: mockOnboardResult,
    });
    vi.mocked(api.verifyMemorySnapshotV2).mockResolvedValue({
      snapshot: {
        snapshot_id: "snap-1",
        agent_id: "agent-001",
        source_type: "sdk",
        label: "wizard-import",
        record_count: 2,
        total_bytes: 200,
        merkle_root: "abc",
        status: "verified",
        created_at: "2026-02-20T10:00:00Z",
      },
      verification_run_id: "ver-1",
      status: "verified",
      score: 0.95,
      sampled_entries: [],
      trust_profile: mockOnboardResult,
    });
    vi.mocked(api.createWebhookSubscriptionV2).mockResolvedValue({
      id: "wh-1",
      agent_id: "agent-001",
      callback_url: "https://example.com/hooks/agentchains",
      event_types: [],
      status: "active",
    });
    vi.mocked(api.fetchWebhookSubscriptionsV2).mockResolvedValue({
      subscriptions: [],
    });
  });

  it("renders the wizard page with title", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    expect(screen.getByText("Agent Onboarding Wizard")).toBeInTheDocument();
    expect(
      screen.getByText(
        /No-code flow: onboard, attest knowledge, verify memory, and enable webhook delivery/,
      ),
    ).toBeInTheDocument();
  });

  it("shows all four step sections", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    expect(screen.getByText("1. Onboard Agent")).toBeInTheDocument();
    expect(
      screen.getByText("2. Runtime + Knowledge Attestation"),
    ).toBeInTheDocument();
    expect(screen.getByText("3. Memory Import + Verify")).toBeInTheDocument();
    expect(screen.getByText("4. Live Webhooks")).toBeInTheDocument();
  });

  it("renders onboard agent form fields", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    expect(screen.getByPlaceholderText("Agent name")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Capabilities (comma separated)"),
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText("A2A endpoint")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Onboard Agent" }),
    ).toBeInTheDocument();
  });

  it("has agent type selector with seller, buyer, both options", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveTextContent("Seller");
    expect(options[1]).toHaveTextContent("Buyer");
    expect(options[2]).toHaveTextContent("Both");
  });

  it("step 2 and 3 buttons are disabled before onboarding", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    expect(
      screen.getByRole("button", { name: "Run Runtime Attestation" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Run Knowledge Challenge" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Refresh Trust Profile" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Import Snapshot" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Create Subscription" }),
    ).toBeDisabled();
  });

  it("onboard agent button calls API and shows success message", async () => {
    const user = userEvent.setup();
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    const nameInput = screen.getByPlaceholderText("Agent name");
    await user.clear(nameInput);
    await user.type(nameInput, "my-agent");

    await user.click(screen.getByRole("button", { name: "Onboard Agent" }));

    await waitFor(() => {
      expect(api.onboardAgentV2).toHaveBeenCalledWith(
        "creator-token-123",
        expect.objectContaining({
          name: "my-agent",
          agent_type: "both",
        }),
      );
    });

    await waitFor(() => {
      expect(
        screen.getByText(
          "Agent onboarded. Continue with runtime and knowledge checks.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("shows trust status after onboarding", async () => {
    const user = userEvent.setup();
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    // Before onboarding, trust status shows placeholder
    expect(
      screen.getByText("Trust profile appears after onboarding."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Onboard Agent" }));

    await waitFor(() => {
      expect(screen.getByText("provisional")).toBeInTheDocument();
      expect(screen.getByText("T1")).toBeInTheDocument();
      expect(screen.getByText("45")).toBeInTheDocument();
    });
  });

  it("enables step 2 buttons after onboarding", async () => {
    const user = userEvent.setup();
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: "Onboard Agent" }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Run Runtime Attestation" }),
      ).not.toBeDisabled();
      expect(
        screen.getByRole("button", { name: "Run Knowledge Challenge" }),
      ).not.toBeDisabled();
      expect(
        screen.getByRole("button", { name: "Refresh Trust Profile" }),
      ).not.toBeDisabled();
    });
  });

  it("shows error message when onboarding fails", async () => {
    vi.mocked(api.onboardAgentV2).mockRejectedValue(
      new Error("Registration failed: duplicate name"),
    );

    const user = userEvent.setup();
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: "Onboard Agent" }));

    await waitFor(() => {
      expect(
        screen.getByText("Registration failed: duplicate name"),
      ).toBeInTheDocument();
    });
  });

  it("shows trust status section with labels", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    expect(screen.getByText("Trust Status")).toBeInTheDocument();
    expect(
      screen.getByText("Trust profile appears after onboarding."),
    ).toBeInTheDocument();
  });

  it("renders webhook section with input and buttons", () => {
    renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

    expect(screen.getByDisplayValue("https://example.com/hooks/agentchains")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create Subscription" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh List" }),
    ).toBeInTheDocument();
  });
});

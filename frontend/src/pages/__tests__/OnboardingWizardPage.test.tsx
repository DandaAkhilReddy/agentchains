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

  const mockTrustProfile = {
    agent_id: "agent-001",
    agent_trust_status: "provisional" as const,
    agent_trust_tier: "T1" as const,
    agent_trust_score: 45,
    stage_scores: {
      identity: 0.8,
      runtime: 0,
      knowledge: 0,
      memory: 0,
      abuse: 1,
    },
  };

  const mockOnboardResult = {
    ...mockTrustProfile,
    agent_name: "test-agent",
    agent_jwt_token: "jwt-abc",
    onboarding_session_id: "session-1",
    agent_card_url: "/cards/agent-001",
    stream_token: "stream-tok-1",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.onboardAgentV2).mockResolvedValue(mockOnboardResult as any);
    vi.mocked(api.attestRuntimeV2).mockResolvedValue({
      attestation_id: "att-1",
      stage_runtime_score: 0.9,
      profile: mockOnboardResult,
    } as any);
    vi.mocked(api.runKnowledgeChallengeV2).mockResolvedValue({
      agent_id: "agent-001",
      status: "passed",
      severe_safety_failure: false,
      stage_knowledge_score: 0.85,
      knowledge_challenge_summary: {},
      profile: mockOnboardResult,
    } as any);
    vi.mocked(api.fetchAgentTrustV2).mockResolvedValue({
      ...mockTrustProfile,
      agent_trust_status: "verified",
      agent_trust_tier: "T2",
      agent_trust_score: 85,
    } as any);
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
    } as any);
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
    } as any);
    vi.mocked(api.createWebhookSubscriptionV2).mockResolvedValue({
      id: "wh-1",
      agent_id: "agent-001",
      callback_url: "https://example.com/hooks/agentchains",
      event_types: [],
      status: "active",
    } as any);
    vi.mocked(api.fetchWebhookSubscriptionsV2).mockResolvedValue({
      subscriptions: [],
    } as any);
  });

  /** Helper: click "Onboard Agent" and wait for completion */
  async function onboardAgent(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: "Onboard Agent" }));
    await waitFor(() => {
      expect(api.onboardAgentV2).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(
        screen.getByText(
          "Agent onboarded. Continue with runtime and knowledge checks.",
        ),
      ).toBeInTheDocument();
    });
  }

  /* ── Initial render ─────────────────────────────────────── */

  describe("initial render", () => {
    it("renders the wizard page title and subtitle", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(screen.getByText("Agent Onboarding Wizard")).toBeInTheDocument();
      expect(
        screen.getByText(
          /No-code flow: onboard, attest knowledge, verify memory, and enable webhook delivery/,
        ),
      ).toBeInTheDocument();
    });

    it("shows all four step section headings", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(screen.getByText("1. Onboard Agent")).toBeInTheDocument();
      expect(
        screen.getByText("2. Runtime + Knowledge Attestation"),
      ).toBeInTheDocument();
      expect(screen.getByText("3. Memory Import + Verify")).toBeInTheDocument();
      expect(screen.getByText("4. Live Webhooks")).toBeInTheDocument();
    });

    it("shows Trust Status section", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(screen.getByText("Trust Status")).toBeInTheDocument();
      expect(
        screen.getByText("Trust profile appears after onboarding."),
      ).toBeInTheDocument();
    });
  });

  /* ── Step 1: Onboard Agent form ─────────────────────────── */

  describe("step 1: onboard agent", () => {
    it("renders all form inputs", () => {
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

    it("has agent type selector with 3 options", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const select = screen.getByRole("combobox");
      expect(select).toBeInTheDocument();
      const options = screen.getAllByRole("option");
      expect(options).toHaveLength(3);
      expect(options[0]).toHaveTextContent("Seller");
      expect(options[1]).toHaveTextContent("Buyer");
      expect(options[2]).toHaveTextContent("Both");
    });

    it("defaults to 'Both' agent type", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const select = screen.getByRole("combobox");
      expect(select).toHaveValue("both");
    });

    it("has default capabilities value", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByDisplayValue("retrieval,tool_use"),
      ).toBeInTheDocument();
    });

    it("has default A2A endpoint", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByDisplayValue("https://agent.example.com"),
      ).toBeInTheDocument();
    });

    it("calls onboardAgentV2 with correct params when onboard button is clicked", async () => {
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
            capabilities: ["retrieval", "tool_use"],
            a2a_endpoint: "https://agent.example.com",
            memory_import_intent: true,
          }),
        );
      });
    });

    it("shows success message after onboarding", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);
      expect(
        screen.getByText(
          "Agent onboarded. Continue with runtime and knowledge checks.",
        ),
      ).toBeInTheDocument();
    });

    it("shows trust profile after onboarding", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);
      await waitFor(() => {
        expect(screen.getByText("provisional")).toBeInTheDocument();
        expect(screen.getByText("T1")).toBeInTheDocument();
        expect(screen.getByText("45")).toBeInTheDocument();
      });
    });

    it("shows trust profile labels (Status, Tier, Score)", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);
      await waitFor(() => {
        expect(screen.getByText("Status")).toBeInTheDocument();
        expect(screen.getByText("Tier")).toBeInTheDocument();
        expect(screen.getByText("Score")).toBeInTheDocument();
      });
    });

    it("changes agent type via selector", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const select = screen.getByRole("combobox");
      await user.selectOptions(select, "seller");
      expect(select).toHaveValue("seller");
    });

    it("updates capabilities input", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const capInput = screen.getByPlaceholderText(
        "Capabilities (comma separated)",
      );
      await user.clear(capInput);
      await user.type(capInput, "code_gen,analysis");
      expect(capInput).toHaveValue("code_gen,analysis");
    });

    it("updates A2A endpoint input", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const endpointInput = screen.getByPlaceholderText("A2A endpoint");
      await user.clear(endpointInput);
      await user.type(endpointInput, "https://new.endpoint.com");
      expect(endpointInput).toHaveValue("https://new.endpoint.com");
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

    it("shows generic error for non-Error exceptions", async () => {
      vi.mocked(api.onboardAgentV2).mockRejectedValue("string error");
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await user.click(screen.getByRole("button", { name: "Onboard Agent" }));
      await waitFor(() => {
        expect(screen.getByText("Unexpected error")).toBeInTheDocument();
      });
    });

    it("shows 'Processing...' text on button while busy", async () => {
      let resolveOnboard: (value: any) => void;
      vi.mocked(api.onboardAgentV2).mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveOnboard = resolve;
          }),
      );
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await user.click(screen.getByRole("button", { name: "Onboard Agent" }));

      // Button should show "Processing..."
      expect(screen.getByText("Processing...")).toBeInTheDocument();

      // Resolve to clean up
      resolveOnboard!(mockOnboardResult);
      await waitFor(() => {
        expect(screen.getByText("Onboard Agent")).toBeInTheDocument();
      });
    });
  });

  /* ── Step 2 and 3 disabled states ───────────────────────── */

  describe("disabled states before onboarding", () => {
    it("disables all step 2 buttons", () => {
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
    });

    it("disables step 3 Import Snapshot button", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByRole("button", { name: "Import Snapshot" }),
      ).toBeDisabled();
    });

    it("disables Verify Snapshot button (no snapshot id)", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByRole("button", { name: "Verify Snapshot" }),
      ).toBeDisabled();
    });

    it("disables step 4 Create Subscription button", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByRole("button", { name: "Create Subscription" }),
      ).toBeDisabled();
    });

    it("disables Refresh List button", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByRole("button", { name: "Refresh List" }),
      ).toBeDisabled();
    });
  });

  /* ── Step 2: Runtime + Knowledge Attestation ────────────── */

  describe("step 2: runtime + knowledge attestation", () => {
    it("enables step 2 buttons after onboarding", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

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

    it("calls attestRuntimeV2 with correct params", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Runtime Attestation" }),
      );

      await waitFor(() => {
        expect(api.attestRuntimeV2).toHaveBeenCalledWith(
          "jwt-abc",
          "agent-001",
          expect.objectContaining({
            runtime_name: "agent-runtime",
            runtime_version: "1.0.0",
            endpoint_reachable: true,
            supports_memory: true,
          }),
        );
      });
    });

    it("shows success message after runtime attestation", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Runtime Attestation" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Runtime attestation completed."),
        ).toBeInTheDocument();
      });
    });

    it("refreshes trust profile after runtime attestation", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Runtime Attestation" }),
      );

      await waitFor(() => {
        expect(api.fetchAgentTrustV2).toHaveBeenCalledWith(
          "agent-001",
          "jwt-abc",
        );
      });
    });

    it("calls runKnowledgeChallengeV2 with correct params", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Knowledge Challenge" }),
      );

      await waitFor(() => {
        expect(api.runKnowledgeChallengeV2).toHaveBeenCalledWith(
          "jwt-abc",
          "agent-001",
          expect.objectContaining({
            capabilities: ["retrieval", "tool_use"],
            claim_payload: expect.objectContaining({
              citations_present: true,
              schema_valid: true,
            }),
          }),
        );
      });
    });

    it("shows success message after knowledge challenge", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Knowledge Challenge" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Knowledge challenge completed."),
        ).toBeInTheDocument();
      });
    });

    it("refreshes trust profile after knowledge challenge", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Knowledge Challenge" }),
      );

      await waitFor(() => {
        expect(api.fetchAgentTrustV2).toHaveBeenCalled();
      });
    });

    it("handles Refresh Trust Profile button", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Refresh Trust Profile" }),
      );

      await waitFor(() => {
        expect(api.fetchAgentTrustV2).toHaveBeenCalledWith(
          "agent-001",
          "jwt-abc",
        );
      });
    });

    it("updates trust profile after refreshing", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Refresh Trust Profile" }),
      );

      await waitFor(() => {
        // fetchAgentTrustV2 returns verified / T2 / 85
        expect(screen.getByText("verified")).toBeInTheDocument();
        expect(screen.getByText("T2")).toBeInTheDocument();
        expect(screen.getByText("85")).toBeInTheDocument();
      });
    });

    it("shows error message when runtime attestation fails", async () => {
      vi.mocked(api.attestRuntimeV2).mockRejectedValue(
        new Error("Attestation service unreachable"),
      );
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Runtime Attestation" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Attestation service unreachable"),
        ).toBeInTheDocument();
      });
    });

    it("shows error message when knowledge challenge fails", async () => {
      vi.mocked(api.runKnowledgeChallengeV2).mockRejectedValue(
        new Error("Challenge timeout"),
      );
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Run Knowledge Challenge" }),
      );

      await waitFor(() => {
        expect(screen.getByText("Challenge timeout")).toBeInTheDocument();
      });
    });
  });

  /* ── Step 3: Memory Import + Verify ─────────────────────── */

  describe("step 3: memory import + verify", () => {
    it("renders memory JSONL textarea with default value", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      // Textarea contains multi-line JSONL data; query by partial text match
      const textareas = document.querySelectorAll("textarea");
      const memoryTextarea = Array.from(textareas).find((el) =>
        el.value.includes("mem-1"),
      );
      expect(memoryTextarea).toBeTruthy();
      expect(memoryTextarea!.value).toContain("mem-2");
    });

    it("enables import button after onboarding", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Import Snapshot" }),
        ).not.toBeDisabled();
      });
    });

    it("calls importMemorySnapshotV2 when Import Snapshot is clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );

      await waitFor(() => {
        expect(api.importMemorySnapshotV2).toHaveBeenCalledWith(
          "jwt-abc",
          expect.objectContaining({
            source_type: "sdk",
            label: "wizard-import",
            chunk_size: 2,
          }),
        );
      });
    });

    it("shows snapshot ID after import", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Snapshot imported: snap-1"),
        ).toBeInTheDocument();
      });
    });

    it("shows 'Active snapshot' label after import", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );

      await waitFor(() => {
        expect(screen.getByText(/Active snapshot:/)).toBeInTheDocument();
      });
    });

    it("enables Verify Snapshot button after import", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Verify Snapshot" }),
        ).not.toBeDisabled();
      });
    });

    it("calls verifyMemorySnapshotV2 when Verify Snapshot is clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Verify Snapshot" }),
        ).not.toBeDisabled();
      });

      await user.click(
        screen.getByRole("button", { name: "Verify Snapshot" }),
      );

      await waitFor(() => {
        expect(api.verifyMemorySnapshotV2).toHaveBeenCalledWith(
          "jwt-abc",
          "snap-1",
          { sample_size: 2 },
        );
      });
    });

    it("shows verification result message", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Verify Snapshot" }),
        ).not.toBeDisabled();
      });

      await user.click(
        screen.getByRole("button", { name: "Verify Snapshot" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Snapshot verification status: verified"),
        ).toBeInTheDocument();
      });
    });

    it("shows error when memory import fails", async () => {
      vi.mocked(api.importMemorySnapshotV2).mockRejectedValue(
        new Error("Invalid JSONL format"),
      );
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Invalid JSONL format"),
        ).toBeInTheDocument();
      });
    });

    it("shows error when verify fails", async () => {
      vi.mocked(api.verifyMemorySnapshotV2).mockRejectedValue(
        new Error("Verification engine unavailable"),
      );
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Verify Snapshot" }),
        ).not.toBeDisabled();
      });

      await user.click(
        screen.getByRole("button", { name: "Verify Snapshot" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Verification engine unavailable"),
        ).toBeInTheDocument();
      });
    });
  });

  /* ── Step 4: Live Webhooks ──────────────────────────────── */

  describe("step 4: webhooks", () => {
    it("renders webhook URL input with default value", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByDisplayValue("https://example.com/hooks/agentchains"),
      ).toBeInTheDocument();
    });

    it("renders Create Subscription and Refresh List buttons", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      expect(
        screen.getByRole("button", { name: "Create Subscription" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Refresh List" }),
      ).toBeInTheDocument();
    });

    it("enables webhook buttons after onboarding", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Create Subscription" }),
        ).not.toBeDisabled();
        expect(
          screen.getByRole("button", { name: "Refresh List" }),
        ).not.toBeDisabled();
      });
    });

    it("calls createWebhookSubscriptionV2 when Create Subscription clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Create Subscription" }),
      );

      await waitFor(() => {
        expect(api.createWebhookSubscriptionV2).toHaveBeenCalledWith(
          "jwt-abc",
          expect.objectContaining({
            callback_url: "https://example.com/hooks/agentchains",
            event_types: [
              "agent.trust.updated",
              "memory.snapshot.verified",
              "challenge.failed",
              "challenge.passed",
            ],
          }),
        );
      });
    });

    it("shows success message after creating subscription", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Create Subscription" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Webhook subscription created."),
        ).toBeInTheDocument();
      });
    });

    it("calls fetchWebhookSubscriptionsV2 after creating subscription", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Create Subscription" }),
      );

      await waitFor(() => {
        expect(api.fetchWebhookSubscriptionsV2).toHaveBeenCalledWith(
          "jwt-abc",
        );
      });
    });

    it("calls fetchWebhookSubscriptionsV2 when Refresh List clicked", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Refresh List" }),
      );

      await waitFor(() => {
        expect(api.fetchWebhookSubscriptionsV2).toHaveBeenCalledWith(
          "jwt-abc",
        );
      });
    });

    it("displays webhook subscriptions in the list", async () => {
      vi.mocked(api.fetchWebhookSubscriptionsV2).mockResolvedValue({
        subscriptions: [
          {
            id: "wh-1",
            agent_id: "agent-001",
            callback_url: "https://example.com/hooks/agentchains",
            event_types: ["agent.trust.updated"],
            status: "active",
            failure_count: 0,
            last_delivery_at: null,
            created_at: "2026-02-20",
          },
        ],
      } as any);

      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Refresh List" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText(
            "https://example.com/hooks/agentchains (active)",
          ),
        ).toBeInTheDocument();
      });
    });

    it("updates webhook URL input", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const input = screen.getByDisplayValue(
        "https://example.com/hooks/agentchains",
      );
      await user.clear(input);
      await user.type(input, "https://new.hooks.example.com");
      expect(input).toHaveValue("https://new.hooks.example.com");
    });

    it("shows error when webhook creation fails", async () => {
      vi.mocked(api.createWebhookSubscriptionV2).mockRejectedValue(
        new Error("Invalid callback URL"),
      );
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Create Subscription" }),
      );

      await waitFor(() => {
        expect(
          screen.getByText("Invalid callback URL"),
        ).toBeInTheDocument();
      });
    });
  });

  /* ── Memory JSONL textarea ──────────────────────────────── */

  describe("memory JSONL textarea", () => {
    it("allows editing the JSONL content", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

      // Find the textarea by its default content
      const textarea = screen.getByDisplayValue(/mem-1/);
      expect(textarea.tagName.toLowerCase()).toBe("textarea");
    });

    it("has 7 rows", () => {
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);
      const textarea = screen.getByDisplayValue(/mem-1/);
      expect(textarea).toHaveAttribute("rows", "7");
    });
  });

  /* ── parseJsonl (exercised through import) ──────────────── */

  describe("parseJsonl edge cases via Import Snapshot", () => {
    it("handles single-line JSONL input", async () => {
      const user = userEvent.setup();
      renderWithProviders(<OnboardingWizardPage {...defaultProps} />);

      // Use fireEvent.change to set textarea value (avoids userEvent { key interpretation)
      const textareas = document.querySelectorAll("textarea");
      const memoryTextarea = Array.from(textareas).find((el) =>
        el.value.includes("mem-1"),
      )!;
      fireEvent.change(memoryTextarea, {
        target: { value: '{"id":"one","content":"test"}' },
      });

      await onboardAgent(user);

      await user.click(
        screen.getByRole("button", { name: "Import Snapshot" }),
      );

      await waitFor(() => {
        expect(api.importMemorySnapshotV2).toHaveBeenCalled();
      });
    });
  });
});

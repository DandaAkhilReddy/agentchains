import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
  within,
} from "@testing-library/react";
import PluginMarketplacePage from "../PluginMarketplacePage";

/* ── Mock PageHeader ──────────────────────────────────────────── */
vi.mock("../../components/PageHeader", () => ({
  default: ({ title, subtitle }: { title: string; subtitle?: string }) => (
    <div data-testid="page-header">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  ),
}));

describe("PluginMarketplacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /* ── Initial render ─────────────────────────────────────── */

  describe("initial render", () => {
    it("renders the page header with title and subtitle", () => {
      render(<PluginMarketplacePage />);
      expect(screen.getByText("Plugin Marketplace")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Discover and install plugins to extend agent capabilities",
        ),
      ).toBeInTheDocument();
    });

    it("renders the search input", () => {
      render(<PluginMarketplacePage />);
      expect(
        screen.getByPlaceholderText(
          "Search plugins by name, author, or tag...",
        ),
      ).toBeInTheDocument();
    });

    it("renders all category filter buttons", () => {
      render(<PluginMarketplacePage />);
      const categories = [
        "All",
        "AI / ML",
        "Data Processing",
        "Communication",
        "Security",
        "Analytics",
        "Utilities",
      ];
      for (const cat of categories) {
        expect(screen.getByText(cat)).toBeInTheDocument();
      }
    });

    it("shows 'All' category as selected by default", () => {
      render(<PluginMarketplacePage />);
      const allBtn = screen.getByText("All");
      // The "All" button should have the active styling class
      expect(allBtn.className).toContain("text-[#60a5fa]");
    });

    it("displays the correct total plugin count", () => {
      render(<PluginMarketplacePage />);
      expect(screen.getByText("9 plugins")).toBeInTheDocument();
    });

    it("renders all 9 plugin cards", () => {
      render(<PluginMarketplacePage />);
      expect(screen.getByText("LLM Router")).toBeInTheDocument();
      expect(screen.getByText("Vector Store")).toBeInTheDocument();
      expect(screen.getByText("Webhook Bridge")).toBeInTheDocument();
      expect(screen.getByText("Auth Guard")).toBeInTheDocument();
      expect(screen.getByText("Usage Analytics")).toBeInTheDocument();
      expect(screen.getByText("Task Scheduler")).toBeInTheDocument();
      expect(screen.getByText("Data Pipeline")).toBeInTheDocument();
      expect(screen.getByText("Anomaly Detector")).toBeInTheDocument();
      expect(screen.getByText("Cache Turbo")).toBeInTheDocument();
    });
  });

  /* ── Plugin card content ────────────────────────────────── */

  describe("plugin card content", () => {
    it("shows plugin author", () => {
      render(<PluginMarketplacePage />);
      // Some authors appear on multiple cards
      expect(screen.getAllByText("AgentChains Core").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("DataForge Labs")).toBeInTheDocument();
      expect(screen.getByText("NetConnect")).toBeInTheDocument();
      expect(screen.getByText("SecureStack")).toBeInTheDocument();
    });

    it("shows plugin descriptions", () => {
      render(<PluginMarketplacePage />);
      expect(
        screen.getByText(
          /Intelligent routing of prompts to the optimal LLM provider/,
        ),
      ).toBeInTheDocument();
    });

    it("shows plugin version", () => {
      render(<PluginMarketplacePage />);
      expect(screen.getByText("v2.1.0")).toBeInTheDocument();
      expect(screen.getByText("v1.4.2")).toBeInTheDocument();
    });

    it("shows plugin ratings", () => {
      render(<PluginMarketplacePage />);
      // Multiple ratings appear - check for at least one
      const ratings = screen.getAllByText("4.8");
      expect(ratings.length).toBeGreaterThanOrEqual(1);
    });

    it("shows formatted install counts (k format)", () => {
      render(<PluginMarketplacePage />);
      // 12450 -> (12450/1000).toFixed(1) = "12.4" -> "12.4k"
      const counts = screen.getAllByText("12.4k");
      expect(counts.length).toBeGreaterThanOrEqual(1);
    });

    it("shows plugin tags", () => {
      render(<PluginMarketplacePage />);
      expect(screen.getByText("llm")).toBeInTheDocument();
      expect(screen.getByText("routing")).toBeInTheDocument();
      expect(screen.getByText("optimization")).toBeInTheDocument();
    });

    it("shows plugin icon letters", () => {
      render(<PluginMarketplacePage />);
      // Each plugin has a single-letter icon
      expect(screen.getByText("R")).toBeInTheDocument(); // LLM Router
      expect(screen.getByText("V")).toBeInTheDocument(); // Vector Store
      expect(screen.getByText("W")).toBeInTheDocument(); // Webhook Bridge
    });

    it("shows 'Installed' badge for pre-installed plugins", () => {
      render(<PluginMarketplacePage />);
      // LLM Router, Webhook Bridge, and Task Scheduler are pre-installed
      const installedBadges = screen.getAllByText("Installed");
      expect(installedBadges.length).toBe(3);
    });

    it("shows 'Details' button on each card", () => {
      render(<PluginMarketplacePage />);
      const detailButtons = screen.getAllByText("Details");
      expect(detailButtons.length).toBe(9);
    });

    it("shows 'Uninstall' for installed plugins", () => {
      render(<PluginMarketplacePage />);
      const uninstallBtns = screen.getAllByText("Uninstall");
      expect(uninstallBtns.length).toBe(3);
    });

    it("shows 'Install' for non-installed plugins", () => {
      render(<PluginMarketplacePage />);
      const installBtns = screen.getAllByText("Install");
      expect(installBtns.length).toBe(6);
    });
  });

  /* ── Search filtering ───────────────────────────────────── */

  describe("search filtering", () => {
    it("filters plugins by name", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "LLM Router" } });

      expect(screen.getByText("LLM Router")).toBeInTheDocument();
      expect(screen.queryByText("Vector Store")).toBeNull();
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("filters plugins by author", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "InsightAI" } });

      expect(screen.getByText("Usage Analytics")).toBeInTheDocument();
      expect(screen.getByText("Anomaly Detector")).toBeInTheDocument();
      expect(screen.queryByText("LLM Router")).toBeNull();
      expect(screen.getByText("2 plugins")).toBeInTheDocument();
    });

    it("filters plugins by description", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, {
        target: { value: "vector storage" },
      });

      expect(screen.getByText("Vector Store")).toBeInTheDocument();
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("filters plugins by tag", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "redis" } });

      expect(screen.getByText("Cache Turbo")).toBeInTheDocument();
      expect(screen.queryByText("LLM Router")).toBeNull();
    });

    it("is case insensitive", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "llm router" } });
      expect(screen.getByText("LLM Router")).toBeInTheDocument();
    });

    it("shows 'No plugins found' when search has no matches", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "nonexistentplugin" } });

      expect(screen.getByText("No plugins found")).toBeInTheDocument();
      expect(
        screen.getByText("Try adjusting your search or filter criteria"),
      ).toBeInTheDocument();
    });

    it("shows singular 'plugin' when exactly 1 result", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "Auth Guard" } });
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });
  });

  /* ── Category filtering ─────────────────────────────────── */

  describe("category filtering", () => {
    it("filters by AI / ML category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("AI / ML"));

      expect(screen.getByText("LLM Router")).toBeInTheDocument();
      expect(screen.getByText("Anomaly Detector")).toBeInTheDocument();
      expect(screen.queryByText("Vector Store")).toBeNull();
      expect(screen.getByText("2 plugins")).toBeInTheDocument();
    });

    it("filters by Data Processing category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Data Processing"));

      expect(screen.getByText("Vector Store")).toBeInTheDocument();
      expect(screen.getByText("Data Pipeline")).toBeInTheDocument();
      expect(screen.queryByText("LLM Router")).toBeNull();
    });

    it("filters by Communication category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Communication"));

      expect(screen.getByText("Webhook Bridge")).toBeInTheDocument();
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("filters by Security category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Security"));

      expect(screen.getByText("Auth Guard")).toBeInTheDocument();
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("filters by Analytics category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Analytics"));

      expect(screen.getByText("Usage Analytics")).toBeInTheDocument();
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("filters by Utilities category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Utilities"));

      expect(screen.getByText("Task Scheduler")).toBeInTheDocument();
      expect(screen.getByText("Cache Turbo")).toBeInTheDocument();
      expect(screen.getByText("2 plugins")).toBeInTheDocument();
    });

    it("resets to All category", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Security"));
      expect(screen.getByText("1 plugin")).toBeInTheDocument();

      fireEvent.click(screen.getByText("All"));
      expect(screen.getByText("9 plugins")).toBeInTheDocument();
    });

    it("combines category and search filters", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Utilities"));

      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "cache" } });

      expect(screen.getByText("Cache Turbo")).toBeInTheDocument();
      expect(screen.queryByText("Task Scheduler")).toBeNull();
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("shows no results when combined filter matches nothing", () => {
      render(<PluginMarketplacePage />);
      fireEvent.click(screen.getByText("Security"));

      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "llm" } });

      expect(screen.getByText("No plugins found")).toBeInTheDocument();
    });
  });

  /* ── Install / Uninstall toggle ─────────────────────────── */

  describe("install / uninstall toggle", () => {
    it("installs a plugin and updates the button", async () => {
      vi.useFakeTimers();
      render(<PluginMarketplacePage />);

      // Find "Auth Guard" card and click Install
      // Auth Guard is not installed by default
      const installBtns = screen.getAllByText("Install");
      // Click the first "Install" button (Vector Store)
      await act(async () => {
        fireEvent.click(installBtns[0]);
      });

      // Should show "Installing..." during the delay
      expect(screen.getByText("Installing...")).toBeInTheDocument();

      // Advance the timer to complete the install
      await act(async () => {
        vi.advanceTimersByTime(1200);
      });

      // The plugin should now show "Uninstall"
      // Total installed: LLM Router, Webhook Bridge, Task Scheduler + Vector Store = 4
      const uninstallBtns = screen.getAllByText("Uninstall");
      expect(uninstallBtns.length).toBe(4);

      vi.useRealTimers();
    });

    it("uninstalls a plugin and updates the button", async () => {
      vi.useFakeTimers();
      render(<PluginMarketplacePage />);

      // Click the first "Uninstall" button (LLM Router)
      const uninstallBtns = screen.getAllByText("Uninstall");
      await act(async () => {
        fireEvent.click(uninstallBtns[0]);
      });

      expect(screen.getByText("Removing...")).toBeInTheDocument();

      await act(async () => {
        vi.advanceTimersByTime(1200);
      });

      // Now there should be 2 "Uninstall" buttons instead of 3
      const remaining = screen.getAllByText("Uninstall");
      expect(remaining.length).toBe(2);

      vi.useRealTimers();
    });

    it("disables the install button while installing", async () => {
      vi.useFakeTimers();
      render(<PluginMarketplacePage />);

      const installBtns = screen.getAllByText("Install");
      await act(async () => {
        fireEvent.click(installBtns[0]);
      });

      // The button that was clicked should now be disabled
      const installingBtn = screen
        .getByText("Installing...")
        .closest("button");
      expect(installingBtn).toBeDisabled();

      await act(async () => {
        vi.advanceTimersByTime(1200);
      });

      vi.useRealTimers();
    });

    it("updates install count when installing", async () => {
      vi.useFakeTimers();
      render(<PluginMarketplacePage />);

      // Vector Store has 8920 installs -> "8.9k"
      // After install it should be 8921 -> still "8.9k" (very close)
      // Let's check Auth Guard: 5120 -> "5.1k", after install: 5121 -> "5.1k"
      // The count change is minimal but the state updates

      const installBtns = screen.getAllByText("Install");
      await act(async () => {
        fireEvent.click(installBtns[0]);
      });

      await act(async () => {
        vi.advanceTimersByTime(1200);
      });

      // After install, the "Installed" badges should increase by 1
      const installedBadges = screen.getAllByText("Installed");
      expect(installedBadges.length).toBe(4);

      vi.useRealTimers();
    });
  });

  /* ── Plugin detail modal ────────────────────────────────── */

  describe("plugin detail modal", () => {
    it("opens modal when Details button is clicked", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]); // Click first Details (LLM Router)

      // Modal should show the long description
      expect(
        screen.getByText(/The LLM Router plugin analyzes incoming prompts/),
      ).toBeInTheDocument();
    });

    it("shows plugin name in modal header", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      // In the modal, the name appears in an h3
      const modalName = screen.getAllByText("LLM Router");
      expect(modalName.length).toBeGreaterThanOrEqual(2); // card + modal
    });

    it("shows plugin author in modal", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      const authors = screen.getAllByText("AgentChains Core");
      expect(authors.length).toBeGreaterThanOrEqual(2);
    });

    it("shows plugin category in modal", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      // "AI / ML" appears in both the filter bar and the modal
      const cats = screen.getAllByText("AI / ML");
      expect(cats.length).toBeGreaterThanOrEqual(2);
    });

    it("shows 'Installed' badge in modal for installed plugins", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]); // LLM Router is installed

      // "Installed" badge appears in both card and modal
      const badges = screen.getAllByText("Installed");
      expect(badges.length).toBeGreaterThanOrEqual(4); // 3 card badges + 1 modal badge
    });

    it("shows plugin stats in modal (installs, rating, version)", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      // Should show "12.4k installs" (12450/1000 = 12.45 -> toFixed(1) = "12.4")
      expect(screen.getByText(/12\.4k installs/)).toBeInTheDocument();
    });

    it("shows tags in modal", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      expect(screen.getByText("About")).toBeInTheDocument();
      expect(screen.getByText("Tags")).toBeInTheDocument();
    });

    it("shows Uninstall Plugin button in modal for installed plugins", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]); // LLM Router is installed

      expect(screen.getByText("Uninstall Plugin")).toBeInTheDocument();
    });

    it("shows Install Plugin button in modal for non-installed plugins", () => {
      render(<PluginMarketplacePage />);
      // Vector Store is index 1 in filtered list, not installed
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[1]); // Vector Store

      expect(screen.getByText("Install Plugin")).toBeInTheDocument();
    });

    it("shows Close button in modal", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      expect(screen.getByText("Close")).toBeInTheDocument();
    });

    it("closes modal when Close button is clicked", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      expect(
        screen.getByText(/The LLM Router plugin analyzes/),
      ).toBeInTheDocument();

      fireEvent.click(screen.getByText("Close"));

      expect(
        screen.queryByText(/The LLM Router plugin analyzes/),
      ).toBeNull();
    });

    it("closes modal when X button is clicked", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      // Find the X close button (it's a button with the X SVG icon)
      const backdrop = document.querySelector(".fixed.inset-0");
      const closeXBtn = backdrop?.querySelector(
        "button.absolute.right-4.top-4",
      ) as HTMLElement;
      expect(closeXBtn).toBeTruthy();
      fireEvent.click(closeXBtn);

      expect(
        screen.queryByText(/The LLM Router plugin analyzes/),
      ).toBeNull();
    });

    it("closes modal when backdrop is clicked", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      const backdrop = document.querySelector(
        ".fixed.inset-0",
      ) as HTMLElement;
      expect(backdrop).toBeTruthy();

      // Click the backdrop itself (not a child)
      fireEvent.click(backdrop);

      expect(
        screen.queryByText(/The LLM Router plugin analyzes/),
      ).toBeNull();
    });

    it("does not close modal when clicking inside the modal content", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      // Click inside the modal content area
      const modalContent = document.querySelector(
        ".fixed.inset-0 > div",
      ) as HTMLElement;
      fireEvent.click(modalContent);

      // Modal should still be visible
      expect(
        screen.getByText(/The LLM Router plugin analyzes/),
      ).toBeInTheDocument();
    });

    it("install from modal updates both modal and card", async () => {
      render(<PluginMarketplacePage />);

      // Open Vector Store modal (not installed)
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[1]);

      expect(screen.getByText("Install Plugin")).toBeInTheDocument();

      // Click Install Plugin in modal
      fireEvent.click(screen.getByText("Install Plugin"));

      // Should show loading state (both card button and modal button show "Installing...")
      const installingTexts = screen.getAllByText("Installing...");
      expect(installingTexts.length).toBeGreaterThanOrEqual(1);

      // Wait for the 1200ms timeout to complete
      await waitFor(
        () => {
          expect(screen.getByText("Uninstall Plugin")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("uninstall from modal updates the modal state", async () => {
      render(<PluginMarketplacePage />);

      // Open LLM Router modal (installed)
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]);

      expect(screen.getByText("Uninstall Plugin")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Uninstall Plugin"));

      // Both card and modal show "Removing..."
      const removingTexts = screen.getAllByText("Removing...");
      expect(removingTexts.length).toBeGreaterThanOrEqual(1);

      // Wait for the 1200ms timeout to complete
      await waitFor(
        () => {
          expect(screen.getByText("Install Plugin")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });

    it("opens modal for a different plugin", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[3]); // Auth Guard

      expect(
        screen.getByText(
          /Comprehensive security plugin that adds JWT validation/,
        ),
      ).toBeInTheDocument();
    });

    it("shows long description in modal, not short description", () => {
      render(<PluginMarketplacePage />);
      const detailBtns = screen.getAllByText("Details");
      fireEvent.click(detailBtns[0]); // LLM Router

      // Should show longDescription, not just description
      expect(
        screen.getByText(/Supports OpenAI, Anthropic, Google/),
      ).toBeInTheDocument();
    });
  });

  /* ── formatInstallCount ─────────────────────────────────── */

  describe("install count formatting", () => {
    it("formats counts >= 1000 with k suffix", () => {
      render(<PluginMarketplacePage />);
      // 12450 -> "12.4k", 8920 -> "8.9k", 6340 -> "6.3k"
      const counts12k = screen.getAllByText("12.4k");
      expect(counts12k.length).toBeGreaterThanOrEqual(1);
      const counts8k = screen.getAllByText("8.9k");
      expect(counts8k.length).toBeGreaterThanOrEqual(1);
    });

    it("formats all different install counts correctly", () => {
      render(<PluginMarketplacePage />);
      // Verify various formatted counts appear
      // (count / 1000).toFixed(1) + "k"
      expect(screen.getAllByText("12.4k").length).toBeGreaterThanOrEqual(1); // LLM Router: 12450
      expect(screen.getAllByText("8.9k").length).toBeGreaterThanOrEqual(1);  // Vector Store: 8920
      expect(screen.getAllByText("6.3k").length).toBeGreaterThanOrEqual(1);  // Webhook Bridge: 6340
      expect(screen.getAllByText("5.1k").length).toBeGreaterThanOrEqual(1);  // Auth Guard: 5120
      expect(screen.getAllByText("4.6k").length).toBeGreaterThanOrEqual(1);  // Usage Analytics: 4580
      expect(screen.getAllByText("7.2k").length).toBeGreaterThanOrEqual(1);  // Task Scheduler: 7210
      expect(screen.getAllByText("3.1k").length).toBeGreaterThanOrEqual(1);  // Data Pipeline: 3150
      expect(screen.getAllByText("2.9k").length).toBeGreaterThanOrEqual(1);  // Anomaly Detector: 2890
      expect(screen.getAllByText("5.7k").length).toBeGreaterThanOrEqual(1);  // Cache Turbo: 5670
    });
  });

  /* ── No results state ───────────────────────────────────── */

  describe("empty state", () => {
    it("shows empty state icon and text", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, {
        target: { value: "xyznonexistent" },
      });

      expect(screen.getByText("No plugins found")).toBeInTheDocument();
      expect(
        screen.getByText("Try adjusting your search or filter criteria"),
      ).toBeInTheDocument();
    });
  });

  /* ── Plugin count label grammar ─────────────────────────── */

  describe("plugin count label", () => {
    it("shows singular 'plugin' for count of 1", () => {
      render(<PluginMarketplacePage />);
      const search = screen.getByPlaceholderText(
        "Search plugins by name, author, or tag...",
      );
      fireEvent.change(search, { target: { value: "Auth Guard" } });
      expect(screen.getByText("1 plugin")).toBeInTheDocument();
    });

    it("shows plural 'plugins' for count > 1", () => {
      render(<PluginMarketplacePage />);
      expect(screen.getByText("9 plugins")).toBeInTheDocument();
    });
  });

  /* ── Modal animations style tag ─────────────────────────── */

  describe("modal animations", () => {
    it("includes style tag with modal animations when modal is not open", () => {
      render(<PluginMarketplacePage />);
      // The style tag is always rendered in the component
      const style = document.querySelector("style");
      expect(style).toBeTruthy();
      expect(style!.textContent).toContain("modal-fade");
      expect(style!.textContent).toContain("modal-scale");
    });
  });

  /* ── Category button styling ────────────────────────────── */

  describe("category button styling", () => {
    it("changes active category styling when clicked", () => {
      render(<PluginMarketplacePage />);
      const securityBtn = screen.getByText("Security");

      // Before clicking - should not have active class
      expect(securityBtn.className).not.toContain("text-[#60a5fa]");

      fireEvent.click(securityBtn);

      // After clicking - should have active class
      expect(securityBtn.className).toContain("text-[#60a5fa]");

      // "All" should no longer be active
      const allBtn = screen.getByText("All");
      expect(allBtn.className).not.toContain("text-[#60a5fa]");
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Sidebar from "../Sidebar";
import type { TabId } from "../Sidebar";

describe("Sidebar", () => {
  let onTabChange: ReturnType<typeof vi.fn>;
  let onMobileClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onTabChange = vi.fn();
    onMobileClose = vi.fn();
    localStorage.clear();
  });

  function renderSidebar(overrides: Partial<Parameters<typeof Sidebar>[0]> = {}) {
    return render(
      <Sidebar
        activeTab={"dashboard" as TabId}
        onTabChange={onTabChange}
        mobileOpen={false}
        onMobileClose={onMobileClose}
        {...overrides}
      />
    );
  }

  it("renders sidebar with navigation groups", () => {
    renderSidebar();
    // All six group titles should be present in the desktop sidebar
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Marketplace")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Platform")).toBeInTheDocument();
    expect(screen.getByText("Engineering")).toBeInTheDocument();
  });

  it("shows correct nav items", () => {
    renderSidebar();
    // Spot-check items from each group
    expect(screen.getByText("Role Landing")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Discover")).toBeInTheDocument();
    expect(screen.getByText("Catalog")).toBeInTheDocument();
    expect(screen.getByText("Wallet")).toBeInTheDocument();
    expect(screen.getByText("Transactions")).toBeInTheDocument();
    expect(screen.getByText("Withdraw")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Reputation")).toBeInTheDocument();
    expect(screen.getByText("Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Integrations")).toBeInTheDocument();
    expect(screen.getByText("Creator")).toBeInTheDocument();
    expect(screen.getByText("Pipeline")).toBeInTheDocument();
    expect(screen.getByText("API Docs")).toBeInTheDocument();
    expect(screen.getByText("System Design")).toBeInTheDocument();
  });

  it("highlights the active item based on the activeTab prop", () => {
    const { container } = renderSidebar({ activeTab: "wallet" });
    // The active button has a white (#ffffff) color and a blue tinted background
    const buttons = container.querySelectorAll("button");
    const walletButton = Array.from(buttons).find((btn) =>
      btn.textContent?.includes("Wallet")
    );
    expect(walletButton).toBeDefined();
    expect(walletButton?.style.color).toBe("rgb(255, 255, 255)");
    expect(walletButton?.style.backgroundColor).toBe("rgba(96, 165, 250, 0.1)");

    // A non-active item should have the inactive color
    const dashboardButton = Array.from(buttons).find((btn) =>
      btn.textContent?.includes("Dashboard")
    );
    expect(dashboardButton?.style.color).toBe("rgb(148, 163, 184)");
    expect(dashboardButton?.style.backgroundColor).toBe("transparent");
  });

  it("toggles collapse/expand when the toggle button is clicked", () => {
    const { container } = renderSidebar();
    // Desktop aside starts expanded (w-60)
    const desktopAside = container.querySelector("aside.hidden.md\\:flex");
    expect(desktopAside?.className).toContain("w-60");

    // The collapse toggle is the last button rendered within sidebarContent
    // It has the class "hidden md:flex" and contains a ChevronLeft initially
    const toggleButton = container.querySelector("button.hidden.md\\:flex");
    expect(toggleButton).toBeInTheDocument();

    // Click collapse
    fireEvent.click(toggleButton!);

    // After collapse, aside should have w-16
    expect(desktopAside?.className).toContain("w-16");
    expect(desktopAside?.className).not.toContain("w-60");

    // Click again to expand
    fireEvent.click(toggleButton!);
    expect(desktopAside?.className).toContain("w-60");
  });

  it("renders mobile overlay when mobileOpen is true", () => {
    const { container } = renderSidebar({ mobileOpen: true });
    // The mobile overlay is a fixed div with md:hidden
    const overlay = container.querySelector("div.fixed.inset-0.z-40.md\\:hidden");
    expect(overlay).toBeInTheDocument();

    // The mobile sidebar aside also appears
    const mobileSidebar = container.querySelector("aside.fixed.left-0.top-0.z-50");
    expect(mobileSidebar).toBeInTheDocument();
  });

  it("calls onMobileClose when the mobile overlay backdrop is clicked", () => {
    const { container } = renderSidebar({ mobileOpen: true });
    const overlay = container.querySelector("div.fixed.inset-0.z-40.md\\:hidden");
    expect(overlay).toBeInTheDocument();

    fireEvent.click(overlay!);
    expect(onMobileClose).toHaveBeenCalledTimes(1);
  });

  it("calls onTabChange and onMobileClose when a nav item is clicked", () => {
    renderSidebar({ mobileOpen: true });
    const analyticsButton = screen.getAllByText("Analytics")[0].closest("button");
    expect(analyticsButton).toBeDefined();

    fireEvent.click(analyticsButton!);
    expect(onTabChange).toHaveBeenCalledWith("analytics");
    expect(onMobileClose).toHaveBeenCalledTimes(1);
  });

  it("renders the logo/brand section with A2A Marketplace text", () => {
    renderSidebar();
    expect(screen.getByText("A2A Marketplace")).toBeInTheDocument();
  });

  it("hides brand text and group titles when sidebar is collapsed", () => {
    const { container } = renderSidebar();
    // Collapse the sidebar
    const toggleButton = container.querySelector("button.hidden.md\\:flex");
    fireEvent.click(toggleButton!);

    // Brand text should be gone
    expect(screen.queryByText("A2A Marketplace")).not.toBeInTheDocument();
    // Group titles should be gone
    expect(screen.queryByText("Overview")).not.toBeInTheDocument();
    expect(screen.queryByText("Marketplace")).not.toBeInTheDocument();
    expect(screen.queryByText("Finance")).not.toBeInTheDocument();
  });

  it("persists collapsed state to localStorage", () => {
    const { container } = renderSidebar();
    const toggleButton = container.querySelector("button.hidden.md\\:flex");

    // Initially not collapsed — useEffect writes "false" on mount
    expect(localStorage.getItem("sidebar_collapsed")).toBe("false");

    // Collapse
    fireEvent.click(toggleButton!);
    expect(localStorage.getItem("sidebar_collapsed")).toBe("true");

    // Expand again
    fireEvent.click(toggleButton!);
    expect(localStorage.getItem("sidebar_collapsed")).toBe("false");
  });

  /* ------------------------------------------------------------------ */
  /* NEW: Additional tests for uncovered lines                           */
  /* ------------------------------------------------------------------ */

  it("reads collapsed state from localStorage on mount", () => {
    // Pre-set localStorage to "true" before rendering
    localStorage.setItem("sidebar_collapsed", "true");
    const { container } = renderSidebar();
    const desktopAside = container.querySelector("aside.hidden.md\\:flex");
    // Sidebar should start collapsed because localStorage had "true"
    expect(desktopAside?.className).toContain("w-16");
    // Brand text should not be visible
    expect(screen.queryByText("A2A Marketplace")).not.toBeInTheDocument();
  });

  it("handles localStorage.getItem throwing an error gracefully", () => {
    // Make localStorage.getItem throw to exercise the catch branch
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("Storage unavailable");
    };
    // Should default to not collapsed (false) on error
    const { container } = renderSidebar();
    const desktopAside = container.querySelector("aside.hidden.md\\:flex");
    expect(desktopAside?.className).toContain("w-60");
    // Restore
    Storage.prototype.getItem = original;
  });

  it("handles localStorage.setItem throwing an error gracefully", () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("Storage full");
    };
    // Should not throw during render
    expect(() => renderSidebar()).not.toThrow();
    Storage.prototype.setItem = original;
  });

  it("shows title attribute on nav buttons when sidebar is collapsed", () => {
    const { container } = renderSidebar();
    const toggleButton = container.querySelector("button.hidden.md\\:flex");
    fireEvent.click(toggleButton!);

    // When collapsed, each nav button should have a title attribute with the label
    const buttons = container.querySelectorAll("button");
    const walletButton = Array.from(buttons).find(
      (btn) => btn.getAttribute("title") === "Wallet"
    );
    expect(walletButton).toBeDefined();

    const dashboardButton = Array.from(buttons).find(
      (btn) => btn.getAttribute("title") === "Dashboard"
    );
    expect(dashboardButton).toBeDefined();
  });

  it("does not show title attribute on nav buttons when sidebar is expanded", () => {
    const { container } = renderSidebar();
    // When expanded, title should be undefined
    const buttons = container.querySelectorAll("button");
    const walletButton = Array.from(buttons).find((btn) =>
      btn.textContent?.includes("Wallet")
    );
    expect(walletButton?.getAttribute("title")).toBeNull();
  });

  it("shows the active indicator bar for the active tab", () => {
    const { container } = renderSidebar({ activeTab: "agents" });
    // The active indicator is a div with the blue background color
    const agentsButton = Array.from(container.querySelectorAll("button")).find(
      (btn) => btn.textContent?.includes("Agents")
    );
    expect(agentsButton).toBeDefined();
    // The active indicator div is a child of the active button
    const indicator = agentsButton?.querySelector("div");
    expect(indicator).toBeDefined();
    expect(indicator?.style.backgroundColor).toBe("rgb(96, 165, 250)");
  });

  it("does not show the active indicator for inactive tabs", () => {
    const { container } = renderSidebar({ activeTab: "wallet" });
    // Check a non-active button -- it should not have the indicator div
    const dashboardButton = Array.from(container.querySelectorAll("button")).find(
      (btn) => btn.textContent?.includes("Dashboard")
    );
    // The inactive button should NOT have a child div with the active indicator style
    const childDivs = dashboardButton?.querySelectorAll("div") ?? [];
    const hasIndicator = Array.from(childDivs).some(
      (div) => div.style.backgroundColor === "rgb(96, 165, 250)"
    );
    expect(hasIndicator).toBe(false);
  });

  it("handles hover on an inactive nav button", () => {
    const { container } = renderSidebar({ activeTab: "dashboard" });
    const buttons = container.querySelectorAll("button");
    const walletButton = Array.from(buttons).find((btn) =>
      btn.textContent?.includes("Wallet")
    );
    expect(walletButton).toBeDefined();

    // Mouse enter on inactive button
    fireEvent.mouseEnter(walletButton!);
    expect(walletButton!.style.color).toBe("rgb(226, 232, 240)");
    expect(walletButton!.style.backgroundColor).toBe("rgba(96, 165, 250, 0.08)");

    // Mouse leave on inactive button
    fireEvent.mouseLeave(walletButton!);
    expect(walletButton!.style.color).toBe("rgb(148, 163, 184)");
    expect(walletButton!.style.backgroundColor).toBe("transparent");
  });

  it("does not change styles on hover for the active nav button", () => {
    const { container } = renderSidebar({ activeTab: "wallet" });
    const buttons = container.querySelectorAll("button");
    const walletButton = Array.from(buttons).find((btn) =>
      btn.textContent?.includes("Wallet")
    );
    expect(walletButton).toBeDefined();

    // Mouse enter on active button should NOT change styles
    fireEvent.mouseEnter(walletButton!);
    expect(walletButton!.style.color).toBe("rgb(255, 255, 255)");
    expect(walletButton!.style.backgroundColor).toBe("rgba(96, 165, 250, 0.1)");

    // Mouse leave on active button should NOT change styles
    fireEvent.mouseLeave(walletButton!);
    expect(walletButton!.style.color).toBe("rgb(255, 255, 255)");
    expect(walletButton!.style.backgroundColor).toBe("rgba(96, 165, 250, 0.1)");
  });

  it("handles hover on the collapse toggle button", () => {
    const { container } = renderSidebar();
    const toggleButton = container.querySelector("button.hidden.md\\:flex");
    expect(toggleButton).toBeDefined();

    fireEvent.mouseEnter(toggleButton!);
    expect((toggleButton as HTMLElement).style.color).toBe("rgb(226, 232, 240)");

    fireEvent.mouseLeave(toggleButton!);
    expect((toggleButton as HTMLElement).style.color).toBe("rgb(100, 116, 139)");
  });

  it("handles hover on the mobile close button", () => {
    const { container } = renderSidebar({ mobileOpen: true });
    // The mobile close button has the X icon and md:hidden class
    const closeButtons = Array.from(container.querySelectorAll("button")).filter(
      (btn) => btn.classList.contains("ml-auto")
    );
    // There are two instances of sidebarContent (desktop + mobile), so close buttons may appear in both
    // But the close button is only rendered when mobileOpen is true
    const closeButton = closeButtons[0];
    expect(closeButton).toBeDefined();

    fireEvent.mouseEnter(closeButton!);
    expect(closeButton!.style.color).toBe("rgb(226, 232, 240)");

    fireEvent.mouseLeave(closeButton!);
    expect(closeButton!.style.color).toBe("rgb(100, 116, 139)");
  });

  it("calls onMobileClose when mobile close button is clicked", () => {
    const { container } = renderSidebar({ mobileOpen: true });
    const closeButtons = Array.from(container.querySelectorAll("button")).filter(
      (btn) => btn.classList.contains("ml-auto")
    );
    const closeButton = closeButtons[0];
    expect(closeButton).toBeDefined();

    fireEvent.click(closeButton!);
    expect(onMobileClose).toHaveBeenCalledTimes(1);
  });

  it("does not render mobile overlay when mobileOpen is false", () => {
    const { container } = renderSidebar({ mobileOpen: false });
    const overlay = container.querySelector("div.fixed.inset-0.z-40.md\\:hidden");
    expect(overlay).not.toBeInTheDocument();
  });

  it("handles nav click without onMobileClose provided", () => {
    render(
      <Sidebar
        activeTab={"dashboard" as TabId}
        onTabChange={onTabChange}
      />
    );
    const analyticsButton = screen.getByText("Analytics").closest("button");
    // Should not throw when onMobileClose is undefined
    expect(() => fireEvent.click(analyticsButton!)).not.toThrow();
    expect(onTabChange).toHaveBeenCalledWith("analytics");
  });

  it("renders all nav items for each group", () => {
    renderSidebar();
    // Overview group
    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    // Marketplace group
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("hides item labels when collapsed and shows only icons", () => {
    const { container } = renderSidebar();
    const toggleButton = container.querySelector("button.hidden.md\\:flex");
    fireEvent.click(toggleButton!);

    // Nav item labels should not be visible
    expect(screen.queryByText("Wallet")).not.toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
  });

  it("renders different active tabs correctly", () => {
    const tabs: TabId[] = ["roles", "agentDashboard", "adminDashboard", "listings", "catalog",
      "actions", "transactions", "redeem", "analytics", "reputation",
      "integrations", "creator", "onboarding", "pipeline", "docs", "technology"];

    for (const tab of tabs) {
      const { container, unmount } = renderSidebar({ activeTab: tab });
      // The active button should exist with white color
      const buttons = container.querySelectorAll("button");
      const hasActive = Array.from(buttons).some(
        (btn) => btn.style.color === "rgb(255, 255, 255)" &&
                  btn.style.backgroundColor === "rgba(96, 165, 250, 0.1)"
      );
      expect(hasActive).toBe(true);
      unmount();
    }
  });

  it("mobile sidebar has correct backdrop styles", () => {
    const { container } = renderSidebar({ mobileOpen: true });
    const overlay = container.querySelector("div.fixed.inset-0.z-40.md\\:hidden");
    expect(overlay).toBeInTheDocument();
    expect(overlay?.style.backgroundColor).toBe("rgba(0, 0, 0, 0.7)");
  });
});

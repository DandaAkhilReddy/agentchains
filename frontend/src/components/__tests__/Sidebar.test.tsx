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
});

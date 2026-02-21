import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Settings, Users, Home } from "lucide-react";
import TabNav, { type Tab } from "../TabNav";

const sampleTabs: Tab[] = [
  { id: "overview", label: "Overview" },
  { id: "agents", label: "Agents" },
  { id: "settings", label: "Settings" },
];

const tabsWithIcons: Tab[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "users", label: "Users", icon: Users },
  { id: "settings", label: "Settings", icon: Settings },
];

describe("TabNav", () => {
  it("renders all tab labels", () => {
    const onChange = vi.fn();
    render(<TabNav tabs={sampleTabs} activeTab="overview" onTabChange={onChange} />);

    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("highlights the active tab with the active text color", () => {
    const onChange = vi.fn();
    render(<TabNav tabs={sampleTabs} activeTab="agents" onTabChange={onChange} />);

    const agentsButton = screen.getByText("Agents").closest("button");
    expect(agentsButton?.className).toContain("text-[#60a5fa]");

    const overviewButton = screen.getByText("Overview").closest("button");
    expect(overviewButton?.className).toContain("text-[#64748b]");
  });

  it("renders the active indicator bar on the active tab", () => {
    const onChange = vi.fn();
    const { container } = render(
      <TabNav tabs={sampleTabs} activeTab="overview" onTabChange={onChange} />
    );

    // The active indicator is a span with bg-[#60a5fa] inside the active button
    const activeButton = screen.getByText("Overview").closest("button");
    const indicator = activeButton?.querySelector(".bg-\\[\\#60a5fa\\]");
    expect(indicator).toBeInTheDocument();

    // Inactive tabs should NOT have the indicator
    const inactiveButton = screen.getByText("Agents").closest("button");
    const noIndicator = inactiveButton?.querySelector(".bg-\\[\\#60a5fa\\]");
    expect(noIndicator).not.toBeInTheDocument();
  });

  it("calls onTabChange with the correct tab id when clicked", () => {
    const onChange = vi.fn();
    render(<TabNav tabs={sampleTabs} activeTab="overview" onTabChange={onChange} />);

    fireEvent.click(screen.getByText("Settings"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("settings");
  });

  it("calls onTabChange for each tab click", () => {
    const onChange = vi.fn();
    render(<TabNav tabs={sampleTabs} activeTab="overview" onTabChange={onChange} />);

    fireEvent.click(screen.getByText("Agents"));
    fireEvent.click(screen.getByText("Settings"));
    fireEvent.click(screen.getByText("Overview"));

    expect(onChange).toHaveBeenCalledTimes(3);
    expect(onChange).toHaveBeenNthCalledWith(1, "agents");
    expect(onChange).toHaveBeenNthCalledWith(2, "settings");
    expect(onChange).toHaveBeenNthCalledWith(3, "overview");
  });

  it("renders icons when tabs have icon props", () => {
    const onChange = vi.fn();
    const { container } = render(
      <TabNav tabs={tabsWithIcons} activeTab="home" onTabChange={onChange} />
    );

    // Each tab button should contain an SVG icon
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(3);
    buttons.forEach((button) => {
      const svg = button.querySelector("svg");
      expect(svg).toBeInTheDocument();
    });
  });

  it("does not render icons when tabs have no icon prop", () => {
    const onChange = vi.fn();
    const { container } = render(
      <TabNav tabs={sampleTabs} activeTab="overview" onTabChange={onChange} />
    );

    const buttons = container.querySelectorAll("button");
    buttons.forEach((button) => {
      const svg = button.querySelector("svg");
      expect(svg).not.toBeInTheDocument();
    });
  });

  it("handles a single tab", () => {
    const onChange = vi.fn();
    const singleTab: Tab[] = [{ id: "only", label: "Only Tab" }];
    render(<TabNav tabs={singleTab} activeTab="only" onTabChange={onChange} />);

    expect(screen.getByText("Only Tab")).toBeInTheDocument();
    const button = screen.getByText("Only Tab").closest("button");
    expect(button?.className).toContain("text-[#60a5fa]");
  });

  it("renders inside a nav element", () => {
    const onChange = vi.fn();
    const { container } = render(
      <TabNav tabs={sampleTabs} activeTab="overview" onTabChange={onChange} />
    );
    const nav = container.querySelector("nav");
    expect(nav).toBeInTheDocument();
  });
});

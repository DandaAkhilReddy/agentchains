import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Settings, Users } from "lucide-react";
import PageHeader from "../PageHeader";

describe("PageHeader", () => {
  it("renders the title", () => {
    render(<PageHeader title="Dashboard" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders the subtitle when provided", () => {
    render(<PageHeader title="Dashboard" subtitle="Overview of your data" />);
    expect(screen.getByText("Overview of your data")).toBeInTheDocument();
  });

  it("does not render subtitle element when subtitle is not provided", () => {
    const { container } = render(<PageHeader title="Dashboard" />);
    const subtitle = container.querySelector(".text-\\[\\#94a3b8\\]");
    expect(subtitle).not.toBeInTheDocument();
  });

  it("renders the icon when provided", () => {
    const { container } = render(<PageHeader title="Settings" icon={Settings} />);
    const iconWrapper = container.querySelector(".rounded-xl");
    expect(iconWrapper).toBeInTheDocument();
    // The icon SVG should be inside the wrapper
    const svg = iconWrapper?.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("does not render icon wrapper when icon is not provided", () => {
    const { container } = render(<PageHeader title="Dashboard" />);
    const iconWrapper = container.querySelector(".rounded-xl");
    expect(iconWrapper).not.toBeInTheDocument();
  });

  it("renders action buttons when provided", () => {
    render(
      <PageHeader
        title="Users"
        actions={<button>Add User</button>}
      />
    );
    expect(screen.getByText("Add User")).toBeInTheDocument();
  });

  it("does not render actions container when actions are not provided", () => {
    const { container } = render(<PageHeader title="Dashboard" />);
    // The outer div has flex items-start justify-between
    // Actions wrapper has flex items-center gap-2
    const actionContainers = container.querySelectorAll(".flex.items-center.gap-2");
    // There is one flex items-center gap-3 for the left side, but gap-2 is actions only
    expect(actionContainers.length).toBe(0);
  });

  it("renders with all props provided", () => {
    const { container } = render(
      <PageHeader
        title="Agent Management"
        subtitle="Manage your AI agents"
        icon={Users}
        actions={
          <>
            <button>Export</button>
            <button>Create</button>
          </>
        }
      />
    );

    expect(screen.getByText("Agent Management")).toBeInTheDocument();
    expect(screen.getByText("Manage your AI agents")).toBeInTheDocument();
    expect(container.querySelector(".rounded-xl")).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
    expect(screen.getByText("Create")).toBeInTheDocument();
  });

  it("renders title inside an h1 element with gradient-text class", () => {
    const { container } = render(<PageHeader title="My Page" />);
    const h1 = container.querySelector("h1");
    expect(h1).toBeInTheDocument();
    expect(h1?.textContent).toBe("My Page");
    expect(h1?.className).toContain("gradient-text");
  });

  it("handles minimal props (title only)", () => {
    const { container } = render(<PageHeader title="Minimal" />);
    expect(screen.getByText("Minimal")).toBeInTheDocument();
    // No icon wrapper
    expect(container.querySelector(".rounded-xl")).not.toBeInTheDocument();
    // No subtitle
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });
});

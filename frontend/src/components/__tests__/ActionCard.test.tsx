import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ActionCard from "../ActionCard";
import type { WebMCPAction } from "../../hooks/useActions";

/* ── Helper: build a valid WebMCPAction with sensible defaults ── */

function makeAction(overrides: Partial<WebMCPAction> = {}): WebMCPAction {
  return {
    id: "action-1",
    title: "Scrape Website",
    description: "Extract structured data from any public webpage.",
    price_per_execution: 0.25,
    tags: ["scraping", "ai"],
    access_count: 1420,
    status: "active",
    domain: "example.com",
    ...overrides,
  };
}

describe("ActionCard", () => {
  it("renders card with title", () => {
    render(<ActionCard action={makeAction()} onExecute={vi.fn()} />);
    expect(screen.getByText("Scrape Website")).toBeInTheDocument();
  });

  it("renders description", () => {
    render(<ActionCard action={makeAction()} onExecute={vi.fn()} />);
    expect(
      screen.getByText("Extract structured data from any public webpage."),
    ).toBeInTheDocument();
  });

  it("shows price/cost formatted to two decimals", () => {
    render(
      <ActionCard
        action={makeAction({ price_per_execution: 1.5 })}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText("1.50")).toBeInTheDocument();
  });

  it("displays tags as badges", () => {
    render(
      <ActionCard
        action={makeAction({ tags: ["automation", "finance", "data"] })}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText("automation")).toBeInTheDocument();
    expect(screen.getByText("finance")).toBeInTheDocument();
    expect(screen.getByText("data")).toBeInTheDocument();
  });

  it("shows status indicator with correct color for each status", () => {
    const statusMap: Record<string, string> = {
      active: "rgb(52, 211, 153)",
      inactive: "rgb(148, 163, 184)",
      deprecated: "rgb(248, 113, 113)",
      beta: "rgb(251, 191, 36)",
    };

    for (const [status, expectedColor] of Object.entries(statusMap)) {
      const { unmount } = render(
        <ActionCard action={makeAction({ status })} onExecute={vi.fn()} />,
      );
      const dot = screen.getByTitle(status);
      expect(dot).toBeInTheDocument();
      expect(dot.style.backgroundColor).toBe(expectedColor);
      unmount();
    }
  });

  it("execute button calls onExecute callback with action id", () => {
    const onExecute = vi.fn();
    render(
      <ActionCard
        action={makeAction({ id: "abc-42" })}
        onExecute={onExecute}
      />,
    );

    const btn = screen.getByRole("button", { name: /execute/i });
    fireEvent.click(btn);
    expect(onExecute).toHaveBeenCalledTimes(1);
    expect(onExecute).toHaveBeenCalledWith("abc-42");
  });

  it("omits description when it is an empty string", () => {
    const { container } = render(
      <ActionCard
        action={makeAction({ description: "" })}
        onExecute={vi.fn()}
      />,
    );
    // The <p> that holds the description should not be rendered
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs.length).toBe(0);
  });

  it("handles missing optional props gracefully", () => {
    const action = makeAction({
      domain: undefined,
      category: undefined,
      created_at: undefined,
      tags: [],
      description: "",
    });
    const { container } = render(
      <ActionCard action={action} onExecute={vi.fn()} />,
    );
    // Card still renders with title and execute button
    expect(screen.getByText(action.title)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /execute/i })).toBeInTheDocument();
    // No description paragraph
    expect(container.querySelectorAll("p").length).toBe(0);
    // No domain span (11px text)
    const domainSpan = container.querySelector(".text-\\[11px\\]");
    expect(domainSpan).not.toBeInTheDocument();
  });

  it("displays access count with locale formatting", () => {
    render(
      <ActionCard
        action={makeAction({ access_count: 9500 })}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText("9,500")).toBeInTheDocument();
  });

  it("shows overflow indicator when more than 4 tags exist", () => {
    const tags = ["scraping", "ai", "data", "finance", "automation", "security"];
    render(
      <ActionCard action={makeAction({ tags })} onExecute={vi.fn()} />,
    );
    // First four should be visible
    expect(screen.getByText("scraping")).toBeInTheDocument();
    expect(screen.getByText("ai")).toBeInTheDocument();
    expect(screen.getByText("data")).toBeInTheDocument();
    expect(screen.getByText("finance")).toBeInTheDocument();
    // Overflow indicator: "+2"
    expect(screen.getByText(/\+2/)).toBeInTheDocument();
  });

  it("card onMouseEnter sets border color and box shadow (lines 50-53)", () => {
    const { container } = render(
      <ActionCard action={makeAction()} onExecute={vi.fn()} />,
    );
    // The card is the outermost div with the group class
    const card = container.firstElementChild as HTMLDivElement;
    expect(card).toBeTruthy();

    // Cover lines 50-53: onMouseEnter sets borderColor and boxShadow
    // jsdom normalizes rgba() values with spaces, so use toHaveStyle for robust comparison
    fireEvent.mouseEnter(card);
    expect(card).toHaveStyle({ borderColor: "rgba(96,165,250,0.3)" });
    expect(card.style.boxShadow).toBe("0 0 24px rgba(96,165,250,0.08)");
  });

  it("card onMouseLeave resets border color and box shadow (lines 55-58)", () => {
    const { container } = render(
      <ActionCard action={makeAction()} onExecute={vi.fn()} />,
    );
    const card = container.firstElementChild as HTMLDivElement;

    // First hover, then leave
    fireEvent.mouseEnter(card);
    // Cover lines 55-58: onMouseLeave resets styles
    fireEvent.mouseLeave(card);
    expect(card).toHaveStyle({ borderColor: "rgba(96,165,250,0.12)" });
    expect(card.style.boxShadow).toBe("none");
  });

  it("execute button onMouseEnter sets box shadow (lines 139-140)", () => {
    const { container } = render(
      <ActionCard action={makeAction()} onExecute={vi.fn()} />,
    );
    const executeBtn = screen.getByRole("button", { name: /execute/i });

    // Cover lines 138-141: onMouseEnter sets boxShadow on button
    fireEvent.mouseEnter(executeBtn);
    expect(executeBtn.style.boxShadow).toBe(
      "0 0 24px rgba(96,165,250,0.35), 0 0 48px rgba(52,211,153,0.2)",
    );
  });

  it("execute button onMouseLeave resets box shadow (lines 142-145)", () => {
    const { container } = render(
      <ActionCard action={makeAction()} onExecute={vi.fn()} />,
    );
    const executeBtn = screen.getByRole("button", { name: /execute/i });

    // Hover first, then leave
    fireEvent.mouseEnter(executeBtn);
    // Cover lines 142-145: onMouseLeave resets boxShadow on button
    fireEvent.mouseLeave(executeBtn);
    expect(executeBtn.style.boxShadow).toBe("0 0 0px rgba(96,165,250,0)");
  });
});

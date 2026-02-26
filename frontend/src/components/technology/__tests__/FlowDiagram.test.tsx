import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FlowDiagram, {
  type FlowNode,
  type FlowEdge,
} from "../FlowDiagram";

/* Minimal icon stub that renders an SVG with forwarded props */
const FakeIcon = (props: Record<string, unknown>) => (
  <svg data-testid="node-icon" {...props} />
);

const baseNodes: FlowNode[] = [
  { id: "a", label: "Input", x: 10, y: 20, icon: FakeIcon as any },
  { id: "b", label: "Process", x: 50, y: 50, icon: FakeIcon as any },
  { id: "c", label: "Output", x: 90, y: 80, icon: FakeIcon as any },
];

const baseEdges: FlowEdge[] = [
  { from: "a", to: "b" },
  { from: "b", to: "c" },
];

describe("FlowDiagram", () => {
  it("renders a button for each node", () => {
    render(<FlowDiagram nodes={baseNodes} edges={baseEdges} />);
    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.getByText("Process")).toBeInTheDocument();
    expect(screen.getByText("Output")).toBeInTheDocument();
  });

  it("renders correct number of icon elements", () => {
    render(<FlowDiagram nodes={baseNodes} edges={baseEdges} />);
    const icons = screen.getAllByTestId("node-icon");
    expect(icons).toHaveLength(3);
  });

  it("positions nodes at correct percentage left/top", () => {
    render(<FlowDiagram nodes={baseNodes} edges={baseEdges} />);
    const inputBtn = screen.getByText("Input").closest("button") as HTMLElement;
    expect(inputBtn.style.left).toBe("10%");
    expect(inputBtn.style.top).toBe("20%");

    const processBtn = screen.getByText("Process").closest("button") as HTMLElement;
    expect(processBtn.style.left).toBe("50%");
    expect(processBtn.style.top).toBe("50%");
  });

  it("calls onNodeClick with node id when a node is clicked", () => {
    const onClick = vi.fn();
    render(
      <FlowDiagram nodes={baseNodes} edges={baseEdges} onNodeClick={onClick} />,
    );
    fireEvent.click(screen.getByText("Process"));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith("b");
  });

  it("applies 'active' class to the activeNode button", () => {
    render(
      <FlowDiagram nodes={baseNodes} edges={baseEdges} activeNode="b" />,
    );
    const activeBtn = screen.getByText("Process").closest("button") as HTMLElement;
    expect(activeBtn.className).toContain("active");

    const inactiveBtn = screen.getByText("Input").closest("button") as HTMLElement;
    expect(inactiveBtn.className).not.toContain("active");
  });

  it("renders SVG path elements for each edge", () => {
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={baseEdges} />,
    );
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(2);
  });

  it("renders edge labels as text elements when provided", () => {
    const edges: FlowEdge[] = [
      { from: "a", to: "b", label: "step1" },
      { from: "b", to: "c", label: "step2" },
    ];
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={edges} />,
    );
    const texts = container.querySelectorAll("text");
    expect(texts).toHaveLength(2);
    expect(texts[0].textContent).toBe("step1");
    expect(texts[1].textContent).toBe("step2");
  });

  it("applies animate-flow-dash class to animated edges", () => {
    const edges: FlowEdge[] = [
      { from: "a", to: "b", animated: true },
      { from: "b", to: "c", animated: false },
    ];
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={edges} />,
    );
    const paths = container.querySelectorAll("path");
    expect(paths[0].classList.contains("animate-flow-dash")).toBe(true);
    expect(paths[1].classList.contains("animate-flow-dash")).toBe(false);
  });

  it("uses default height of 400 and accepts custom height", () => {
    const { container, rerender } = render(
      <FlowDiagram nodes={baseNodes} edges={baseEdges} />,
    );
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.style.height).toBe("400px");

    rerender(<FlowDiagram nodes={baseNodes} edges={baseEdges} height={600} />);
    expect(wrapper.style.height).toBe("600px");
  });

  it("applies custom className to the wrapper div", () => {
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={baseEdges} className="my-custom" />,
    );
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain("my-custom");
  });

  it("sets node description as title attribute on button", () => {
    const nodes: FlowNode[] = [
      {
        id: "x",
        label: "Agent",
        x: 50,
        y: 50,
        icon: FakeIcon as any,
        description: "LLM agent node",
      },
    ];
    render(<FlowDiagram nodes={nodes} edges={[]} />);
    const btn = screen.getByText("Agent").closest("button") as HTMLElement;
    expect(btn).toHaveAttribute("title", "LLM agent node");
  });

  it("applies custom color to icon, defaults to blue", () => {
    const nodes: FlowNode[] = [
      { id: "r", label: "Red", x: 20, y: 20, icon: FakeIcon as any, color: "#ff0000" },
      { id: "d", label: "Default", x: 80, y: 80, icon: FakeIcon as any },
    ];
    render(<FlowDiagram nodes={nodes} edges={[]} />);
    const icons = screen.getAllByTestId("node-icon");
    // Custom color node
    expect(icons[0].style.color).toBe("rgb(255, 0, 0)");
    // Default color node
    expect(icons[1].style.color).toBe("rgb(59, 130, 246)");
  });

  it("skips rendering path when edge references unknown node (line 53: !a || !b returns null)", () => {
    // An edge from "nonexistent" to "b" — buildPath returns null, so the path
    // is skipped via `if (!d) return null` on line 105.
    const edgesWithUnknown: FlowEdge[] = [
      { from: "nonexistent-id", to: "b" },
      { from: "a", to: "b" },
    ];
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={edgesWithUnknown} />,
    );
    // Only 1 valid edge (a→b), the other is skipped
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(1);
  });

  it("skips edge label when edge references unknown node (line 83: midpoint fallback)", () => {
    // Edge with a label but referencing a non-existent 'to' node — edgeMidpoint
    // returns the { x: 50, y: 50 } fallback, but since buildPath also returns null
    // the entire edge group is skipped.
    const edgesWithUnknown: FlowEdge[] = [
      { from: "a", to: "unknown-node", label: "orphan" },
    ];
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={edgesWithUnknown} />,
    );
    // The edge is not rendered because buildPath returns null
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(0);
    const texts = container.querySelectorAll("text");
    expect(texts).toHaveLength(0);
  });

  it("handles nodes at the exact same position (len === 0 in buildPath, lines 68-69)", () => {
    // When from and to nodes have the same x,y, len === 0, so px/py use the 0 branch
    const collocatedNodes: FlowNode[] = [
      { id: "p", label: "P", x: 50, y: 50, icon: FakeIcon as any },
      { id: "q", label: "Q", x: 50, y: 50, icon: FakeIcon as any },
    ];
    const edgesCollocated: FlowEdge[] = [{ from: "p", to: "q" }];
    const { container } = render(
      <FlowDiagram nodes={collocatedNodes} edges={edgesCollocated} />,
    );
    // Path should still be rendered (just a degenerate bezier)
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(1);

    // Both node buttons should be present
    expect(screen.getByText("P")).toBeInTheDocument();
    expect(screen.getByText("Q")).toBeInTheDocument();
  });

  it("edge label is positioned at midpoint between nodes", () => {
    const edges: FlowEdge[] = [
      { from: "a", to: "b", label: "connects" },
    ];
    const { container } = render(
      <FlowDiagram nodes={baseNodes} edges={edges} />,
    );
    const text = container.querySelector("text");
    expect(text).toBeInTheDocument();
    expect(text?.textContent).toBe("connects");
    // Midpoint of (10,20) and (50,50) should be x=30, y=35
    expect(text?.getAttribute("x")).toBe("30");
  });

  it("renders empty diagram with no nodes and no edges", () => {
    const { container } = render(
      <FlowDiagram nodes={[]} edges={[]} />,
    );
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(0);
    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(0);
  });

  it("does not call onNodeClick when onNodeClick is undefined", () => {
    // onNodeClick is optional; clicking should not throw
    render(<FlowDiagram nodes={baseNodes} edges={baseEdges} />);
    fireEvent.click(screen.getByText("Process"));
    // If we get here without throwing, the optional chaining worked
    expect(screen.getByText("Process")).toBeInTheDocument();
  });

  it("renders edge label at correct x midpoint between two known nodes (covers edgeMidpoint line 83 happy path)", () => {
    // Both from and to nodes are known → edgeMidpoint returns their midpoint.
    // This exercises the `return { x: (a.x + b.x) / 2, ... }` path (line 84).
    const nodes: FlowNode[] = [
      { id: "start", label: "Start", x: 20, y: 30, icon: FakeIcon as any },
      { id: "end", label: "End", x: 80, y: 70, icon: FakeIcon as any },
    ];
    const edges: FlowEdge[] = [{ from: "start", to: "end", label: "flow" }];
    const { container } = render(
      <FlowDiagram nodes={nodes} edges={edges} />,
    );
    const text = container.querySelector("text");
    expect(text).toBeInTheDocument();
    expect(text?.textContent).toBe("flow");
    // Midpoint: x = (20+80)/2 = 50, y = (30+70)/2 - 1.5 = 48.5
    expect(text?.getAttribute("x")).toBe("50");
  });
});

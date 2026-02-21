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
});

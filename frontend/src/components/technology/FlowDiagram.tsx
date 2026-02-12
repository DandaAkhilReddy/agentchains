import { useCallback, useMemo } from "react";
import type { LucideIcon } from "lucide-react";

export interface FlowNode {
  id: string;
  label: string;
  x: number;
  y: number;
  icon: LucideIcon;
  color?: string;
  description?: string;
}

export interface FlowEdge {
  from: string;
  to: string;
  label?: string;
  animated?: boolean;
}

interface Props {
  nodes: FlowNode[];
  edges: FlowEdge[];
  onNodeClick?: (id: string) => void;
  activeNode?: string;
  height?: number;
  className?: string;
}

/** Reusable SVG-based flow diagram with positioned nodes and animated connecting edges. */
export default function FlowDiagram({
  nodes,
  edges,
  onNodeClick,
  activeNode,
  height = 400,
  className = "",
}: Props) {
  // Build a lookup map from node id to its percentage coordinates
  const nodeMap = useMemo(() => {
    const map = new Map<string, FlowNode>();
    for (const n of nodes) {
      map.set(n.id, n);
    }
    return map;
  }, [nodes]);

  // Build a quadratic bezier path between two node center coordinates (in %)
  const buildPath = useCallback(
    (fromId: string, toId: string): string | null => {
      const a = nodeMap.get(fromId);
      const b = nodeMap.get(toId);
      if (!a || !b) return null;

      const x1 = a.x;
      const y1 = a.y;
      const x2 = b.x;
      const y2 = b.y;

      // Control point: midpoint shifted perpendicular for a gentle curve
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;
      const dx = x2 - x1;
      const dy = y2 - y1;
      const len = Math.sqrt(dx * dx + dy * dy);
      const offset = Math.min(len * 0.15, 8);
      // Perpendicular direction (normalised)
      const px = len > 0 ? -dy / len : 0;
      const py = len > 0 ? dx / len : 0;
      const cx = mx + px * offset;
      const cy = my + py * offset;

      return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
    },
    [nodeMap],
  );

  // Midpoint for edge labels
  const edgeMidpoint = useCallback(
    (fromId: string, toId: string) => {
      const a = nodeMap.get(fromId);
      const b = nodeMap.get(toId);
      if (!a || !b) return { x: 50, y: 50 };
      return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    },
    [nodeMap],
  );

  return (
    <div
      className={`relative w-full ${className}`}
      style={{ height }}
    >
      {/* SVG edge overlay */}
      <svg
        className="absolute inset-0 pointer-events-none"
        width="100%"
        height="100%"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        fill="none"
      >
        {edges.map((edge) => {
          const d = buildPath(edge.from, edge.to);
          if (!d) return null;
          const key = `${edge.from}-${edge.to}`;
          return (
            <g key={key}>
              <path
                d={d}
                stroke="#94a3b8"
                strokeWidth="0.35"
                fill="none"
                className={edge.animated ? "animate-flow-dash" : ""}
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
              />
              {edge.label && (() => {
                const mid = edgeMidpoint(edge.from, edge.to);
                return (
                  <text
                    x={mid.x}
                    y={mid.y - 1.5}
                    textAnchor="middle"
                    className="fill-[#94a3b8]"
                    style={{ fontSize: "2.5px" }}
                  >
                    {edge.label}
                  </text>
                );
              })()}
            </g>
          );
        })}
      </svg>

      {/* Nodes */}
      {nodes.map((node) => {
        const Icon = node.icon;
        const isActive = activeNode === node.id;
        return (
          <button
            key={node.id}
            type="button"
            onClick={() => onNodeClick?.(node.id)}
            className={`glass-card-subtle tech-node px-3 py-2 cursor-pointer flex items-center gap-2 text-xs font-medium absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap ${isActive ? "active" : ""}`}
            style={{
              left: `${node.x}%`,
              top: `${node.y}%`,
            }}
            title={node.description}
          >
            <Icon
              size={14}
              style={{ color: node.color ?? "#3b82f6" }}
              className="shrink-0"
            />
            <span className="text-text-primary">{node.label}</span>
          </button>
        );
      })}
    </div>
  );
}

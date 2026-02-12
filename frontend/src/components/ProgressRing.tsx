interface Props {
  value: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  showLabel?: boolean;
}

const COLORS: Record<string, string> = {
  cyan: "#00d4ff",
  purple: "#8b5cf6",
  green: "#10b981",
  amber: "#f59e0b",
  red: "#ef4444",
};

export default function ProgressRing({
  value,
  size = 48,
  strokeWidth = 4,
  color = "cyan",
  showLabel = true,
}: Props) {
  const resolvedColor = COLORS[color] || color;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(Math.max(value, 0), 100) / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-border-subtle"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={resolvedColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
        />
      </svg>
      {showLabel && (
        <span
          className="absolute text-text-primary font-semibold"
          style={{ fontSize: size * 0.22 }}
        >
          {Math.round(value)}
        </span>
      )}
    </div>
  );
}

interface Props {
  value: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  showLabel?: boolean;
}

const COLORS: Record<string, string> = {
  cyan: "#60a5fa",
  purple: "#a78bfa",
  green: "#34d399",
  amber: "#fbbf24",
  red: "#f87171",
};

function getAutoColor(value: number): string {
  if (value < 30) return "#f87171";
  if (value <= 70) return "#fbbf24";
  return "#34d399";
}

export default function ProgressRing({
  value,
  size = 48,
  strokeWidth = 4,
  color,
  showLabel = true,
}: Props) {
  const clampedValue = Math.min(Math.max(value, 0), 100);

  // If color is provided, resolve it from the map or use it directly.
  // If no color is provided, auto-color based on value.
  const resolvedColor = color
    ? COLORS[color] || color
    : getAutoColor(clampedValue);

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clampedValue / 100) * circumference;

  // Unique filter ID to avoid SVG filter collisions when multiple rings render
  const filterId = `glow-${size}-${Math.round(value)}`;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow
              dx="0"
              dy="0"
              stdDeviation="2.5"
              floodColor={resolvedColor}
              floodOpacity="0.5"
            />
          </filter>
        </defs>
        {/* Track circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1a2035"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle with glow */}
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
          filter={`url(#${filterId})`}
          style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
        />
      </svg>
      {showLabel && (
        <span
          className="absolute font-mono font-semibold text-[#e2e8f0]"
          style={{ fontSize: size * 0.22 }}
        >
          {Math.round(value)}
        </span>
      )}
    </div>
  );
}

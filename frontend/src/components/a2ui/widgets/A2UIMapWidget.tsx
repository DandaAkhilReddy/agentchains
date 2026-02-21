import { useState, useMemo } from "react";
import { MapPin, ZoomIn, ZoomOut, Crosshair } from "lucide-react";

/**
 * A2UI Map Widget.
 *
 * Renders a placeholder SVG map with marker pins, coordinates display,
 * and a marker list. No external map library required.
 */

export interface MapMarker {
  id: string;
  latitude: number;
  longitude: number;
  label?: string;
  color?: string;
}

interface A2UIMapWidgetProps {
  latitude: number;
  longitude: number;
  markers?: MapMarker[];
  zoom?: number;
}

/** Clamp a number between min and max */
function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

/**
 * Convert lat/lng to simple x/y percentage on the SVG canvas.
 * Uses equirectangular projection centered on the provided center coords.
 */
function toSvgCoords(
  lat: number,
  lng: number,
  centerLat: number,
  centerLng: number,
  zoom: number,
) {
  const scale = zoom * 2;
  const x = 50 + ((lng - centerLng) / 360) * 100 * scale;
  const y = 50 - ((lat - centerLat) / 180) * 100 * scale;
  return {
    x: clamp(x, 2, 98),
    y: clamp(y, 2, 98),
  };
}

export default function A2UIMapWidget({
  latitude,
  longitude,
  markers = [],
  zoom = 4,
}: A2UIMapWidgetProps) {
  const [currentZoom, setCurrentZoom] = useState(zoom);
  const [hoveredMarker, setHoveredMarker] = useState<string | null>(null);

  const clampedZoom = clamp(currentZoom, 1, 20);

  // Pre-compute marker positions
  const markerPositions = useMemo(
    () =>
      markers.map((m) => ({
        ...m,
        ...toSvgCoords(m.latitude, m.longitude, latitude, longitude, clampedZoom),
      })),
    [markers, latitude, longitude, clampedZoom],
  );

  // Center dot position
  const center = toSvgCoords(latitude, longitude, latitude, longitude, clampedZoom);

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[rgba(96,165,250,0.1)]">
            <MapPin className="h-3.5 w-3.5 text-[#60a5fa]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#e2e8f0]">Map View</h3>
            <p className="text-[10px] font-mono text-[#64748b]">
              {latitude.toFixed(4)}, {longitude.toFixed(4)}
            </p>
          </div>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCurrentZoom((z) => Math.max(1, z - 1))}
            className="rounded-lg p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
            title="Zoom out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <span className="min-w-[2rem] text-center text-[10px] font-mono text-[#94a3b8]">
            {clampedZoom}x
          </span>
          <button
            onClick={() => setCurrentZoom((z) => Math.min(20, z + 1))}
            className="rounded-lg p-1.5 text-[#64748b] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0]"
            title="Zoom in"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* SVG Map area */}
      <div className="relative bg-[#0d1220] p-2">
        <svg
          viewBox="0 0 100 60"
          className="h-64 w-full"
          style={{ background: "radial-gradient(ellipse at center, #131b2e 0%, #0d1220 100%)" }}
        >
          {/* Grid lines */}
          {Array.from({ length: 9 }).map((_, i) => (
            <line
              key={`h-${i}`}
              x1="0"
              y1={(i + 1) * 6}
              x2="100"
              y2={(i + 1) * 6}
              stroke="rgba(255,255,255,0.04)"
              strokeWidth="0.15"
            />
          ))}
          {Array.from({ length: 15 }).map((_, i) => (
            <line
              key={`v-${i}`}
              x1={(i + 1) * 6.25}
              y1="0"
              x2={(i + 1) * 6.25}
              y2="60"
              stroke="rgba(255,255,255,0.04)"
              strokeWidth="0.15"
            />
          ))}

          {/* Center crosshair */}
          <circle
            cx={center.x}
            cy={center.y * 0.6}
            r="1.2"
            fill="none"
            stroke="#60a5fa"
            strokeWidth="0.3"
            opacity="0.5"
          />
          <line
            x1={center.x - 2}
            y1={center.y * 0.6}
            x2={center.x + 2}
            y2={center.y * 0.6}
            stroke="#60a5fa"
            strokeWidth="0.15"
            opacity="0.4"
          />
          <line
            x1={center.x}
            y1={center.y * 0.6 - 2}
            x2={center.x}
            y2={center.y * 0.6 + 2}
            stroke="#60a5fa"
            strokeWidth="0.15"
            opacity="0.4"
          />

          {/* Markers */}
          {markerPositions.map((m) => {
            const isHovered = hoveredMarker === m.id;
            const pinColor = m.color ?? "#f87171";
            return (
              <g
                key={m.id}
                onMouseEnter={() => setHoveredMarker(m.id)}
                onMouseLeave={() => setHoveredMarker(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Ping ring */}
                <circle
                  cx={m.x}
                  cy={m.y * 0.6}
                  r={isHovered ? "2" : "1.5"}
                  fill="none"
                  stroke={pinColor}
                  strokeWidth="0.2"
                  opacity={isHovered ? 0.6 : 0.3}
                >
                  <animate
                    attributeName="r"
                    values="1.5;3;1.5"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.3;0;0.3"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>

                {/* Pin marker */}
                <circle
                  cx={m.x}
                  cy={m.y * 0.6}
                  r={isHovered ? "1.2" : "0.8"}
                  fill={pinColor}
                  stroke="#0d1220"
                  strokeWidth="0.3"
                  style={{
                    filter: isHovered
                      ? `drop-shadow(0 0 2px ${pinColor})`
                      : undefined,
                    transition: "r 0.2s ease",
                  }}
                />

                {/* Tooltip label */}
                {isHovered && m.label && (
                  <g>
                    <rect
                      x={m.x + 1.5}
                      y={m.y * 0.6 - 3}
                      width={m.label.length * 1.2 + 2}
                      height="4"
                      rx="0.8"
                      fill="#1a2035"
                      stroke="rgba(255,255,255,0.1)"
                      strokeWidth="0.15"
                    />
                    <text
                      x={m.x + 2.5}
                      y={m.y * 0.6 - 0.6}
                      fill="#e2e8f0"
                      fontSize="2"
                      fontFamily="ui-monospace, monospace"
                    >
                      {m.label}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Marker list */}
      {markers.length > 0 && (
        <div className="border-t border-[rgba(255,255,255,0.06)] px-6 py-4">
          <p className="mb-3 text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
            Markers ({markers.length})
          </p>
          <div className="flex flex-col gap-2">
            {markers.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-[rgba(255,255,255,0.02)]"
                onMouseEnter={() => setHoveredMarker(m.id)}
                onMouseLeave={() => setHoveredMarker(null)}
              >
                <div
                  className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                  style={{
                    backgroundColor: m.color ?? "#f87171",
                    boxShadow: `0 0 6px ${m.color ?? "#f87171"}40`,
                  }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-[#e2e8f0] truncate">
                    {m.label ?? m.id}
                  </p>
                </div>
                <div className="flex items-center gap-1 text-[10px] font-mono text-[#64748b]">
                  <Crosshair className="h-2.5 w-2.5" />
                  {m.latitude.toFixed(4)}, {m.longitude.toFixed(4)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inline animations */}
      <style>{`
        @keyframes map-pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

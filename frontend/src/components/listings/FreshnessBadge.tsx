import { Clock } from "lucide-react";
import { relativeTime } from "../../lib/format";

export default function FreshnessBadge({ iso }: { iso: string }) {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = diff / (1000 * 60 * 60);
  const label = relativeTime(iso);

  let color: string;
  let bg: string;
  let glow: string;
  if (hours < 1) {
    color = "#34d399";
    bg = "rgba(52,211,153,0.1)";
    glow = "0 0 6px rgba(52,211,153,0.2)";
  } else if (hours < 24) {
    color = "#60a5fa";
    bg = "rgba(96,165,250,0.1)";
    glow = "0 0 6px rgba(96,165,250,0.15)";
  } else {
    color = "#94a3b8";
    bg = "rgba(148,163,184,0.08)";
    glow = "none";
  }

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{ color, backgroundColor: bg, boxShadow: glow }}
    >
      <Clock className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}

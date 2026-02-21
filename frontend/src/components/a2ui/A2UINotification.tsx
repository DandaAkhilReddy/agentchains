import { useEffect, useState } from "react";
import type { A2UINotifyMessage, A2UINotifyLevel } from "../../types/a2ui";

/**
 * A2UI Notification toast.
 *
 * Auto-dismissing toast notification with level-based styling
 * (info, success, warning, error). Renders a list of active
 * notifications in the bottom-right corner.
 */

interface A2UINotificationProps {
  notifications: A2UINotifyMessage[];
}

const LEVEL_CONFIG: Record<
  A2UINotifyLevel,
  { color: string; icon: string }
> = {
  info: { color: "#60a5fa", icon: "\u2139\uFE0F" },
  success: { color: "#34d399", icon: "\u2705" },
  warning: { color: "#fbbf24", icon: "\u26A0\uFE0F" },
  error: { color: "#f87171", icon: "\u274C" },
};

export default function A2UINotification({
  notifications,
}: A2UINotificationProps) {
  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {notifications.map((notif, idx) => (
        <NotificationToast key={`${notif.title}-${idx}`} notification={notif} />
      ))}
    </div>
  );
}

function NotificationToast({
  notification,
}: {
  notification: A2UINotifyMessage;
}) {
  const { level, title, message, duration_ms } = notification;
  const config = LEVEL_CONFIG[level] ?? LEVEL_CONFIG.info;
  const effectiveDuration = duration_ms ?? 5000;
  const [progress, setProgress] = useState(100);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (effectiveDuration <= 0) return;

    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, 100 - (elapsed / effectiveDuration) * 100);
      setProgress(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
        setVisible(false);
      }
    }, 50);

    return () => clearInterval(interval);
  }, [effectiveDuration]);

  if (!visible) return null;

  return (
    <div
      className="relative min-w-[320px] overflow-hidden rounded-lg px-4 py-3 shadow-lg backdrop-blur-xl animate-slide-in"
      style={{
        background: "rgba(20, 25, 40, 0.95)",
        borderLeft: `4px solid ${config.color}`,
      }}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex-shrink-0 text-sm">{config.icon}</span>
        <div className="flex-1">
          <p className="text-sm font-medium text-[#e2e8f0]">{title}</p>
          {message && (
            <p className="mt-0.5 text-xs text-[#94a3b8]">{message}</p>
          )}
        </div>
        <button
          onClick={() => setVisible(false)}
          className="flex-shrink-0 text-[#64748b] transition-colors hover:text-[#e2e8f0]"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Countdown bar */}
      {effectiveDuration > 0 && (
        <div
          className="absolute bottom-0 left-0 h-[2px] transition-all duration-100 ease-linear"
          style={{
            width: `${progress}%`,
            backgroundColor: config.color,
            opacity: 0.6,
          }}
        />
      )}
    </div>
  );
}

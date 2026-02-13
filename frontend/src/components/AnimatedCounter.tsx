import { useEffect, useRef, useState } from "react";

interface Props {
  value: number;
  duration?: number;
  className?: string;
  glow?: boolean;
}

export default function AnimatedCounter({
  value,
  duration = 600,
  className = "",
  glow = false,
}: Props) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const start = prev.current;
    const delta = value - start;
    if (delta === 0) return;
    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(start + delta * eased));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        prev.current = value;
      }
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [value, duration]);

  return (
    <span
      className={`font-mono text-[#e2e8f0] ${className}`}
      style={
        glow
          ? { textShadow: "0 0 10px rgba(96,165,250,0.3), 0 0 20px rgba(96,165,250,0.1)" }
          : undefined
      }
    >
      {display.toLocaleString()}
    </span>
  );
}

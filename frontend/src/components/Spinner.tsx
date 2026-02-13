interface Props {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZES: Record<string, { box: string; border: string }> = {
  sm: { box: "h-4 w-4", border: "border-[1.5px]" },
  md: { box: "h-5 w-5", border: "border-2" },
  lg: { box: "h-8 w-8", border: "border-[3px]" },
};

export default function Spinner({ size = "md", label }: Props) {
  const s = SIZES[size];

  return (
    <div className="inline-flex items-center gap-2">
      <div
        className={`animate-spin rounded-full border-[#60a5fa] border-t-transparent ${s.box} ${s.border}`}
        style={{
          boxShadow: "0 0 10px rgba(96, 165, 250, 0.3)",
        }}
        role="status"
        aria-label={label || "Loading"}
      />
      {label && <span className="text-sm text-[#94a3b8]">{label}</span>}
    </div>
  );
}

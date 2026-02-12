interface Props {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZES = {
  sm: "h-4 w-4 border-[1.5px]",
  md: "h-5 w-5 border-2",
  lg: "h-8 w-8 border-[3px]",
};

export default function Spinner({ size = "md", label }: Props) {
  return (
    <div className="inline-flex items-center gap-2">
      <div
        className={`animate-spin rounded-full border-border-subtle border-t-primary shadow-[0_0_8px_rgba(0,212,255,0.3)] ${SIZES[size]}`}
        role="status"
        aria-label={label || "Loading"}
      />
      {label && <span className="text-sm text-text-muted">{label}</span>}
    </div>
  );
}

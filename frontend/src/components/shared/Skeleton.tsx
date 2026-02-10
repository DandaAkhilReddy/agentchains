interface Props {
  className?: string;
  lines?: number;
  circle?: boolean;
}

export function Skeleton({ className = "", lines = 1, circle }: Props) {
  if (circle) {
    return <div className={`skeleton rounded-full ${className}`} />;
  }
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton h-4"
          style={{ width: i === lines - 1 && lines > 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

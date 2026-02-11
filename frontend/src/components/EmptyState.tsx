interface Props {
  message?: string;
}

export default function EmptyState({ message = "No data found" }: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle py-16">
      <div className="text-2xl text-text-muted">∅</div>
      <p className="mt-2 text-sm text-text-secondary">{message}</p>
    </div>
  );
}

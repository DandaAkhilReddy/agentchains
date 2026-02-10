interface Props {
  message?: string;
}

export default function EmptyState({ message = "No data found" }: Props) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 py-16">
      <div className="text-2xl text-zinc-700">∅</div>
      <p className="mt-2 text-sm text-zinc-500">{message}</p>
    </div>
  );
}

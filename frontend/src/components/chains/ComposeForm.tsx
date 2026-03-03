import { useState } from "react";
import { Wand2, ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  onCompose: (taskDescription: string, maxPrice?: number, minQuality?: number) => Promise<void>;
  loading: boolean;
}

export default function ComposeForm({ onCompose, loading }: Props) {
  const [task, setTask] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxPrice, setMaxPrice] = useState("");
  const [minQuality, setMinQuality] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || loading) return;
    await onCompose(
      task.trim(),
      maxPrice ? parseFloat(maxPrice) : undefined,
      minQuality ? parseFloat(minQuality) : undefined,
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1.5 block text-sm font-medium text-[#e2e8f0]">
          Describe what you want your agent chain to do
        </label>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. Write pytest edge cases for my FastAPI auth module, then review them for correctness and security..."
          rows={4}
          className="w-full rounded-xl border bg-transparent px-4 py-3 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        />
        <p className="mt-1 text-xs text-[#475569]">
          Keywords: search, analyze, summarize, report, compliance, test, review, judge
        </p>
      </div>

      <button
        type="button"
        onClick={() => setShowAdvanced((p) => !p)}
        className="flex items-center gap-1 text-xs text-[#60a5fa] hover:text-[#93bbfc] transition-colors"
      >
        Advanced options {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-[#94a3b8]">Max price (USD)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
              placeholder="No limit"
              className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#60a5fa]"
              style={{ borderColor: "rgba(255,255,255,0.08)" }}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-[#94a3b8]">Min quality (0-1)</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={minQuality}
              onChange={(e) => setMinQuality(e.target.value)}
              placeholder="No filter"
              className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#60a5fa]"
              style={{ borderColor: "rgba(255,255,255,0.08)" }}
            />
          </div>
        </div>
      )}

      <button
        type="submit"
        disabled={!task.trim() || loading}
        className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium text-white transition-all disabled:opacity-40"
        style={{
          background: "linear-gradient(135deg, #60a5fa, #a78bfa)",
          boxShadow: "0 0 16px rgba(96,165,250,0.25)",
        }}
      >
        <Wand2 className="h-4 w-4" />
        {loading ? "Composing..." : "Compose Chain"}
      </button>
    </form>
  );
}

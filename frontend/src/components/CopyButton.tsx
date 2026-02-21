import { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API can fail (e.g. permissions denied) — silently ignore
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[#64748b] hover:text-[#e2e8f0] hover:bg-[rgba(255,255,255,0.04)] transition-all duration-200 active:scale-90"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check size={12} className="text-[#34d399]" />
      ) : (
        <Copy size={12} />
      )}
    </button>
  );
}

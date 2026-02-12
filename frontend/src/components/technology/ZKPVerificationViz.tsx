import { useState } from "react";
import { Shield, GitBranch, FileJson, Filter, Hash } from "lucide-react";

const PROOF_TYPES = [
  {
    icon: GitBranch,
    title: "Merkle Root",
    desc: "SHA-256 content chunks form a Merkle tree. Root hash proves data integrity without revealing content.",
  },
  {
    icon: FileJson,
    title: "Schema Proof",
    desc: "Validates JSON structure (field names, types) without exposing values. Buyers confirm data format pre-purchase.",
  },
  {
    icon: Filter,
    title: "Bloom Filter",
    desc: "256-byte probabilistic filter with 3 hash functions. Check if specific keywords exist in content.",
  },
  {
    icon: Hash,
    title: "Metadata Hash",
    desc: "Cryptographic commitment to size, category, quality score, and freshness timestamp.",
  },
];

function getBloomBits(word: string): number[] {
  const bits: number[] = [];
  for (let seed = 0; seed < 3; seed++) {
    let hash = seed * 31;
    for (let i = 0; i < word.length; i++) {
      hash = ((hash << 5) - hash + word.charCodeAt(i)) | 0;
    }
    bits.push(Math.abs(hash) % 256);
  }
  return [...new Set(bits)];
}

export default function ZKPVerificationViz() {
  const [word, setWord] = useState("");
  const bits = word ? getBloomBits(word) : [];

  return (
    <div className="space-y-6">
      {/* Proof Types Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {PROOF_TYPES.map((p) => {
          const Icon = p.icon;
          return (
            <div key={p.title} className="glass-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-glow">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <h3 className="text-sm font-semibold text-text-primary">
                  {p.title}
                </h3>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">
                {p.desc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Interactive Bloom Filter Demo */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          Interactive Bloom Filter Demo
        </h3>
        <p className="text-xs text-text-muted mb-3">
          Type a word to see which bits would be set in a 256-bit bloom filter
          with 3 hash functions.
        </p>
        <input
          type="text"
          value={word}
          onChange={(e) => setWord(e.target.value)}
          placeholder="Type a keyword..."
          className="w-full max-w-xs rounded-lg bg-surface-overlay/50 border border-border-subtle px-3 py-1.5 text-sm text-text-primary mb-4 focus:border-primary/30 focus:outline-none"
        />
        <div className="flex flex-wrap gap-[2px]">
          {Array.from({ length: 256 }, (_, i) => (
            <div
              key={i}
              className={`h-2.5 w-2.5 rounded-sm transition-colors duration-300 ${
                bits.includes(i)
                  ? "bg-primary shadow-[0_0_4px_rgba(59,130,246,0.5)]"
                  : "bg-surface-overlay"
              }`}
            />
          ))}
        </div>
        {word && (
          <p className="text-xs text-text-muted mt-3">
            Bits set: {bits.join(", ")} -- {bits.length} of 256 bits active
          </p>
        )}
      </div>

      {/* Verification Pipeline */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">
          Verification Pipeline
        </h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {[
            "Query",
            "Bloom Check",
            "Schema Check",
            "Size Check",
            "Quality Check",
            "Verified",
          ].map((step, i, arr) => (
            <div key={step} className="flex items-center gap-2 shrink-0">
              <div
                className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                  i === arr.length - 1
                    ? "bg-success/10 text-success border border-success/20"
                    : "bg-surface-overlay text-text-primary border border-border-subtle"
                }`}
              >
                {step}
              </div>
              {i < arr.length - 1 && (
                <Shield className="h-3 w-3 text-text-muted shrink-0" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

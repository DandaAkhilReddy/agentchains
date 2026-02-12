import { useState } from "react";
import { Search } from "lucide-react";

const MOCK_LISTINGS = [
  { title: "Python FastAPI tutorial", keyword: 0.45, quality: 0.24, freshness: 0.18, spec: 0.1 },
  { title: "Django REST framework", keyword: 0.35, quality: 0.27, freshness: 0.16, spec: 0.1 },
  { title: "Flask web development", keyword: 0.30, quality: 0.21, freshness: 0.14, spec: 0 },
  { title: "Node.js Express guide", keyword: 0.10, quality: 0.28, freshness: 0.19, spec: 0 },
  { title: "React hooks patterns", keyword: 0.05, quality: 0.30, freshness: 0.20, spec: 0 },
];

const FRESH_COSTS = [
  { category: "web_search", fresh: 0.01, cached: 0.003 },
  { category: "code_analysis", fresh: 0.02, cached: 0.005 },
  { category: "document_summary", fresh: 0.015, cached: 0.004 },
  { category: "api_response", fresh: 0.005, cached: 0.002 },
  { category: "computation", fresh: 0.03, cached: 0.008 },
];

export default function AutoMatchViz() {
  const [query, setQuery] = useState("python web framework");

  return (
    <div className="space-y-6">
      {/* Formula */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          Scoring Formula
        </h3>
        <div className="flex flex-wrap items-center gap-1 text-xs font-mono">
          <span className="text-text-secondary">Score =</span>
          <span className="rounded px-1.5 py-0.5 bg-primary/10 text-primary font-bold">
            0.5
          </span>
          <span className="text-text-muted">x keyword</span>
          <span className="text-text-secondary">+</span>
          <span className="rounded px-1.5 py-0.5 bg-secondary/10 text-secondary font-bold">
            0.3
          </span>
          <span className="text-text-muted">x quality</span>
          <span className="text-text-secondary">+</span>
          <span className="rounded px-1.5 py-0.5 bg-success/10 text-success font-bold">
            0.2
          </span>
          <span className="text-text-muted">x freshness</span>
          <span className="text-text-secondary">+</span>
          <span className="rounded px-1.5 py-0.5 bg-warning/10 text-warning font-bold">
            0.1
          </span>
          <span className="text-text-muted">x specialization</span>
        </div>
      </div>

      {/* Interactive Demo */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-3 mb-4">
          <Search className="h-4 w-4 text-text-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 rounded-lg bg-surface-overlay/50 border border-border-subtle px-3 py-1.5 text-sm text-text-primary focus:border-primary/30 focus:outline-none"
            placeholder="Enter search query..."
          />
        </div>
        <div className="space-y-3">
          {MOCK_LISTINGS.map((listing) => {
            const total =
              listing.keyword + listing.quality + listing.freshness + listing.spec;
            return (
              <div key={listing.title}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-text-primary">
                    {listing.title}
                  </span>
                  <span className="text-xs font-mono font-bold text-primary">
                    {total.toFixed(2)}
                  </span>
                </div>
                <div className="h-3 rounded-full overflow-hidden bg-surface-overlay flex animate-grow-bar">
                  <div
                    style={{ width: `${(listing.keyword / 1) * 100}%` }}
                    className="bg-primary"
                  />
                  <div
                    style={{ width: `${(listing.quality / 1) * 100}%` }}
                    className="bg-secondary"
                  />
                  <div
                    style={{ width: `${(listing.freshness / 1) * 100}%` }}
                    className="bg-success"
                  />
                  {listing.spec > 0 && (
                    <div
                      style={{ width: `${(listing.spec / 1) * 100}%` }}
                      className="bg-warning"
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex gap-4 mt-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-primary" />
            Keyword
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-secondary" />
            Quality
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-success" />
            Freshness
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-warning" />
            Specialization
          </span>
        </div>
      </div>

      {/* Cached vs Fresh Cost Table */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          Cached vs Fresh Cost
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border-subtle">
                <th className="text-left py-2">Category</th>
                <th className="text-right py-2">Fresh Cost</th>
                <th className="text-right py-2">Cached Price</th>
                <th className="text-right py-2">Savings</th>
              </tr>
            </thead>
            <tbody>
              {FRESH_COSTS.map((c) => (
                <tr
                  key={c.category}
                  className="border-b border-border-subtle/50"
                >
                  <td className="py-2 font-medium text-text-primary">
                    {c.category.replace(/_/g, " ")}
                  </td>
                  <td className="text-right text-text-secondary">
                    ${c.fresh.toFixed(3)}
                  </td>
                  <td className="text-right text-success">
                    ${c.cached.toFixed(3)}
                  </td>
                  <td className="text-right font-bold text-primary">
                    {((1 - c.cached / c.fresh) * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

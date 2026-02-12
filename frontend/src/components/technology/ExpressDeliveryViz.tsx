import { Zap, Clock, ArrowRight, CheckCircle2 } from "lucide-react";

const TRADITIONAL = [
  { label: "Initiate", ms: 500 },
  { label: "Pay", ms: 2000 },
  { label: "Deliver", ms: 1000 },
  { label: "Verify", ms: 500 },
  { label: "Complete", ms: 200 },
];

const EXPRESS_MS = 85;

export default function ExpressDeliveryViz() {
  const tradTotal = TRADITIONAL.reduce((s, t) => s + t.ms, 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Traditional Flow */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-4 w-4 text-text-muted" />
            <h3 className="text-sm font-semibold text-text-primary">
              Traditional Flow
            </h3>
            <span className="ml-auto text-xs font-mono text-danger">
              {tradTotal}ms total
            </span>
          </div>
          <div className="space-y-2">
            {TRADITIONAL.map((step, i) => (
              <div key={step.label} className="flex items-center gap-3">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-overlay text-[10px] font-bold text-text-muted">
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-text-primary">
                      {step.label}
                    </span>
                    <span className="text-xs font-mono text-text-muted">
                      {step.ms}ms
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-surface-overlay overflow-hidden">
                    <div
                      className="h-full rounded-full bg-text-muted/40 animate-grow-bar"
                      style={{ width: `${(step.ms / tradTotal) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Express Flow */}
        <div className="glass-card border-primary/20 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold gradient-text">
              Express Delivery
            </h3>
            <span className="ml-auto text-xs font-mono text-success">
              &lt;100ms
            </span>
          </div>
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-glow">
                <ArrowRight className="h-6 w-6 text-primary" />
              </div>
              <div className="h-0.5 w-24 bg-gradient-to-r from-primary to-success rounded" />
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-success/10">
                <CheckCircle2 className="h-6 w-6 text-success" />
              </div>
            </div>
          </div>
          <div className="text-center">
            <p className="text-xs text-text-secondary">
              Single request collapses 5 steps into 1
            </p>
            <p className="text-2xl font-bold font-mono gradient-text mt-2">
              {EXPRESS_MS}ms
            </p>
            <p className="text-xs text-text-muted mt-1">
              avg delivery with cache hit
            </p>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {[
              { label: "Init+Pay", val: "3ms" },
              { label: "CDN Fetch", val: "0.1ms" },
              { label: "Commit", val: "2ms" },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-lg bg-surface-overlay/50 p-2 text-center"
              >
                <p className="text-[10px] text-text-muted">{s.label}</p>
                <p className="text-xs font-mono font-bold text-primary">
                  {s.val}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Speedup Summary */}
      <div className="glass-card p-5 text-center">
        <p className="text-xs text-text-muted uppercase tracking-widest mb-2">
          Performance Improvement
        </p>
        <p className="text-4xl font-bold gradient-text">
          {Math.round(tradTotal / EXPRESS_MS)}x
        </p>
        <p className="text-sm text-text-secondary mt-1">
          faster than traditional purchase flow
        </p>
      </div>
    </div>
  );
}

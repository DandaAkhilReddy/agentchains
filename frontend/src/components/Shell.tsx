import type { ReactNode } from "react";

export default function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
              <span className="text-lg">⬡</span>
            </div>
            <span className="text-sm font-semibold tracking-tight">
              A2A Marketplace
            </span>
          </div>
          <span className="ml-3 rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-zinc-400">
            v0.1
          </span>
        </div>
      </header>
      {children}
    </div>
  );
}

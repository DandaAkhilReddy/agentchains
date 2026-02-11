import type { ReactNode } from "react";
import { Hexagon } from "lucide-react";
import TokenBalance from "./TokenBalance";

export default function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-border-glow bg-[rgba(13,17,23,0.6)] backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[rgba(0,212,255,0.12)] to-[rgba(139,92,246,0.12)] transition-colors hover:from-[rgba(0,212,255,0.2)] hover:to-[rgba(139,92,246,0.2)]">
              <Hexagon className="h-4 w-4 text-primary" />
            </div>
            <span className="text-sm font-semibold tracking-tight gradient-text">
              A2A Marketplace
            </span>
          </div>
          <span className="ml-3 rounded-full border border-[rgba(0,212,255,0.2)] bg-primary-glow px-2 py-0.5 text-[10px] font-medium text-primary">
            v0.2
          </span>
          <div className="ml-auto">
            <TokenBalance />
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
      </header>
      {children}
    </div>
  );
}

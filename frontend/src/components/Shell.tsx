import type { ReactNode } from "react";
import { Bell, Menu, Settings } from "lucide-react";
import TokenBalance from "./TokenBalance";

interface Props {
  children: ReactNode;
  onMenuToggle?: () => void;
}

export default function Shell({ children, onMenuToggle }: Props) {
  return (
    <div className="min-h-screen bg-[#0a0e1a]">
      <header className="sticky top-0 z-30 border-b border-[rgba(255,255,255,0.06)] bg-[rgba(10,14,26,0.8)] backdrop-blur-xl">
        <div className="flex h-14 items-center justify-between px-4 md:justify-end md:px-6">
          {/* Mobile hamburger */}
          {onMenuToggle && (
            <button
              onClick={onMenuToggle}
              className="rounded-lg p-2 text-[#64748b] hover:text-[#e2e8f0] hover:bg-[#1a2035] transition-colors md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
          )}
          <div className="flex items-center gap-3">
            <TokenBalance />
            <button className="relative rounded-lg p-2 text-[#64748b] hover:text-[#e2e8f0] hover:bg-[#1a2035] transition-colors">
              <Bell className="h-4 w-4" />
              <span
                className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[#00ff88]"
                style={{ boxShadow: "0 0 6px rgba(0,255,136,0.6)" }}
              />
            </button>
            <button className="rounded-lg p-2 text-[#64748b] hover:text-[#e2e8f0] hover:bg-[#1a2035] transition-colors">
              <Settings className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}

import type { ReactNode } from "react";
import { Bell, Menu, Settings } from "lucide-react";
import TokenBalance from "./TokenBalance";

interface Props {
  children: ReactNode;
  onMenuToggle?: () => void;
}

export default function Shell({ children, onMenuToggle }: Props) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-border-glow bg-[rgba(255,255,255,0.8)] backdrop-blur-xl">
        <div className="flex h-14 items-center justify-between px-4 md:justify-end md:px-6">
          {/* Mobile hamburger */}
          {onMenuToggle && (
            <button
              onClick={onMenuToggle}
              className="rounded-lg p-2 text-text-muted hover:text-text-primary hover:bg-surface-overlay transition-colors md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
          )}
          <div className="flex items-center gap-3">
            <TokenBalance />
            <button className="relative rounded-lg p-2 text-text-muted hover:text-text-primary hover:bg-surface-overlay transition-colors">
              <Bell className="h-4 w-4" />
              <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-primary" />
            </button>
            <button className="rounded-lg p-2 text-text-muted hover:text-text-primary hover:bg-surface-overlay transition-colors">
              <Settings className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}

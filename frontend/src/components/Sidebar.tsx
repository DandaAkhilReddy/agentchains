import { useState, useEffect } from "react";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard, Bot, Store, BookOpen, ArrowLeftRight,
  Wallet, Gift, BarChart3, Trophy, Plug, User,
  ChevronLeft, ChevronRight, Hexagon, X,
} from "lucide-react";

export type TabId =
  | "dashboard" | "agents" | "listings" | "catalog"
  | "transactions" | "wallet" | "redeem"
  | "analytics" | "reputation"
  | "integrations" | "creator";

interface NavItem {
  id: TabId;
  label: string;
  icon: LucideIcon;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    title: "Marketplace",
    items: [
      { id: "agents", label: "Agents", icon: Bot },
      { id: "listings", label: "Discover", icon: Store },
      { id: "catalog", label: "Catalog", icon: BookOpen },
    ],
  },
  {
    title: "Finance",
    items: [
      { id: "wallet", label: "Wallet", icon: Wallet },
      { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
      { id: "redeem", label: "Redeem", icon: Gift },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { id: "analytics", label: "Analytics", icon: BarChart3 },
      { id: "reputation", label: "Reputation", icon: Trophy },
    ],
  },
  {
    title: "Platform",
    items: [
      { id: "integrations", label: "Integrations", icon: Plug },
      { id: "creator", label: "Creator", icon: User },
    ],
  },
];

interface Props {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export default function Sidebar({ activeTab, onTabChange, mobileOpen, onMobileClose }: Props) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("sidebar_collapsed") === "true"; } catch { return false; }
  });

  useEffect(() => {
    try { localStorage.setItem("sidebar_collapsed", String(collapsed)); } catch {}
  }, [collapsed]);

  const handleNav = (id: TabId) => {
    onTabChange(id);
    onMobileClose?.();
  };

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="flex h-14 items-center gap-3 border-b border-border-glow px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary-glow to-secondary-glow">
          <Hexagon className="h-4 w-4 text-primary" />
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight gradient-text whitespace-nowrap">
            A2A Marketplace
          </span>
        )}
        {/* Mobile close button */}
        {mobileOpen && (
          <button
            onClick={onMobileClose}
            className="ml-auto rounded-lg p-1 text-text-muted hover:text-text-primary md:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 scrollbar-thin">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mb-4">
            {!collapsed && (
              <p className="mb-1 px-4 text-[10px] font-semibold uppercase tracking-widest text-text-muted">
                {group.title}
              </p>
            )}
            {group.items.map((item) => {
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNav(item.id)}
                  title={collapsed ? item.label : undefined}
                  className={`group relative flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-all duration-200 ${
                    active
                      ? "text-primary bg-primary-glow"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-overlay/50"
                  }`}
                >
                  {active && (
                    <div className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-primary shadow-[0_0_8px_rgba(59,130,246,0.4)]" />
                  )}
                  <item.icon className={`h-[18px] w-[18px] shrink-0 ${active ? "text-primary" : "text-text-muted group-hover:text-text-secondary"}`} />
                  {!collapsed && (
                    <span className="whitespace-nowrap">{item.label}</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Collapse Toggle — hidden on mobile */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="hidden md:flex h-12 items-center justify-center border-t border-border-glow text-text-muted hover:text-text-primary transition-colors"
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`fixed left-0 top-0 z-40 hidden md:flex h-screen flex-col border-r border-border-glow bg-[rgba(255,255,255,0.85)] backdrop-blur-xl transition-all duration-300 ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={onMobileClose}
          />
          <aside className="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col border-r border-border-glow bg-[rgba(255,255,255,0.92)] backdrop-blur-xl md:hidden animate-slide-in">
            {sidebarContent}
          </aside>
        </>
      )}
    </>
  );
}

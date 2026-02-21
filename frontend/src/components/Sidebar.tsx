import { useState, useEffect } from "react";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard, Bot, Store, BookOpen, ArrowLeftRight,
  Wallet, Gift, BarChart3, Trophy, Plug, User,
  Shield, Zap,
  ChevronLeft, ChevronRight, Hexagon, X,
  GitBranch, FileText, Cpu,
} from "lucide-react";

export type TabId =
  | "roles" | "dashboard" | "agentDashboard" | "adminDashboard" | "agents" | "listings" | "catalog" | "actions"
  | "transactions" | "wallet" | "redeem"
  | "analytics" | "reputation"
  | "integrations" | "creator"
  | "onboarding" | "pipeline" | "docs" | "technology"
  | "interact" | "billing" | "plugins";

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
      { id: "roles", label: "Role Landing", icon: Shield },
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "agentDashboard", label: "Agent", icon: Bot },
      { id: "adminDashboard", label: "Admin", icon: Shield },
    ],
  },
  {
    title: "Marketplace",
    items: [
      { id: "agents", label: "Agents", icon: Bot },
      { id: "listings", label: "Discover", icon: Store },
      { id: "catalog", label: "Catalog", icon: BookOpen },
      { id: "actions", label: "Actions", icon: Zap },
    ],
  },
  {
    title: "Finance",
    items: [
      { id: "wallet", label: "Wallet", icon: Wallet },
      { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
      { id: "redeem", label: "Withdraw", icon: Gift },
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
      { id: "onboarding", label: "Onboarding", icon: Shield },
      { id: "integrations", label: "Integrations", icon: Plug },
      { id: "creator", label: "Creator", icon: User },
    ],
  },
  {
    title: "Engineering",
    items: [
      { id: "pipeline", label: "Pipeline", icon: GitBranch },
      { id: "docs", label: "API Docs", icon: FileText },
      { id: "technology", label: "System Design", icon: Cpu },
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
      <div className="flex h-14 items-center gap-3 px-4"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
          style={{
            background: 'linear-gradient(135deg, rgba(96,165,250,0.15), rgba(167,139,250,0.15))',
            boxShadow: '0 0 12px rgba(96,165,250,0.2)',
          }}
        >
          <Hexagon className="h-4 w-4" style={{ color: '#60a5fa' }} />
        </div>
        {!collapsed && (
          <span
            className="text-sm font-semibold tracking-tight whitespace-nowrap"
            style={{
              background: 'linear-gradient(135deg, #60a5fa, #a78bfa)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            A2A Marketplace
          </span>
        )}
        {/* Mobile close button */}
        {mobileOpen && (
          <button
            onClick={onMobileClose}
            className="ml-auto rounded-lg p-1 md:hidden"
            style={{ color: '#64748b' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#e2e8f0')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#64748b')}
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav
        className="flex-1 overflow-y-auto py-4"
        style={{
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgba(255,255,255,0.08) transparent',
        }}
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mb-4">
            {!collapsed && (
              <p
                className="mb-1 px-4 text-[10px] font-semibold uppercase"
                style={{
                  color: '#64748b',
                  letterSpacing: '0.1em',
                }}
              >
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
                  className="group relative flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-all duration-200"
                  style={{
                    color: active ? '#ffffff' : '#94a3b8',
                    backgroundColor: active
                      ? 'rgba(96,165,250,0.1)'
                      : 'transparent',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      e.currentTarget.style.color = '#e2e8f0';
                      e.currentTarget.style.backgroundColor = 'rgba(96,165,250,0.08)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      e.currentTarget.style.color = '#94a3b8';
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }
                  }}
                >
                  {active && (
                    <div
                      className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r"
                      style={{
                        backgroundColor: '#60a5fa',
                        boxShadow: '0 0 8px rgba(96,165,250,0.5)',
                      }}
                    />
                  )}
                  <item.icon
                    className="h-[18px] w-[18px] shrink-0 transition-colors duration-200"
                    style={{
                      color: active ? '#60a5fa' : '#64748b',
                      filter: active ? 'drop-shadow(0 0 4px rgba(96,165,250,0.4))' : 'none',
                    }}
                  />
                  {!collapsed && (
                    <span className="whitespace-nowrap">{item.label}</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Collapse Toggle -- hidden on mobile */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="hidden md:flex h-12 items-center justify-center transition-colors"
        style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          color: '#64748b',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = '#e2e8f0')}
        onMouseLeave={(e) => (e.currentTarget.style.color = '#64748b')}
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`fixed left-0 top-0 z-40 hidden md:flex h-screen flex-col transition-all duration-300 ${
          collapsed ? "w-16" : "w-60"
        }`}
        style={{
          background: 'linear-gradient(180deg, #0d1220 0%, #0a0e1a 100%)',
          borderRight: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        {sidebarContent}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <>
          <div
            className="fixed inset-0 z-40 md:hidden"
            style={{
              backgroundColor: 'rgba(0,0,0,0.7)',
              backdropFilter: 'blur(4px)',
              WebkitBackdropFilter: 'blur(4px)',
            }}
            onClick={onMobileClose}
          />
          <aside
            className="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col md:hidden animate-slide-in"
            style={{
              background: 'linear-gradient(180deg, #0d1220 0%, #0a0e1a 100%)',
              borderRight: '1px solid rgba(255,255,255,0.1)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
            }}
          >
            {sidebarContent}
          </aside>
        </>
      )}
    </>
  );
}

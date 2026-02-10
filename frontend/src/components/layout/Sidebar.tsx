import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LayoutDashboard, PlusCircle, Settings, MessageSquare, ShieldCheck } from "lucide-react";
import { useAuthStore } from "../../store/authStore";

const ADMIN_EMAILS = ["areddy@hhamedicine.com", "admin@test.com"];

const navItems = [
  { to: "/", icon: LayoutDashboard, labelKey: "nav.dashboard" },
  { to: "/scanner", icon: PlusCircle, labelKey: "nav.addLoan" },
  { to: "/feedback", icon: MessageSquare, labelKey: "nav.feedback" },
  { to: "/settings", icon: Settings, labelKey: "nav.settings" },
];

const adminItem = { to: "/admin", icon: ShieldCheck, labelKey: "nav.admin" };

export function Sidebar() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const isAdmin = ADMIN_EMAILS.includes(user?.email || "");

  const items = isAdmin ? [...navItems, adminItem] : navItems;

  return (
    <aside className="h-[calc(100vh-64px)] sticky top-16 border-r border-[var(--color-border-default)] bg-[var(--color-bg-card)] p-4 transition-colors">
      <nav className="space-y-1">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-[var(--color-sidebar-active)] text-[var(--color-sidebar-active-text)]"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-inset)] hover:text-[var(--color-text-primary)]"
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

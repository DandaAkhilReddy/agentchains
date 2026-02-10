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

export function MobileNav() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const isAdmin = ADMIN_EMAILS.includes(user?.email || "");

  const items = isAdmin ? [...navItems, adminItem] : navItems;

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[var(--color-bg-card)] border-t border-[var(--color-border-default)] px-2 py-1 z-50 transition-colors">
      <div className="flex justify-around">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex flex-col items-center py-1.5 px-2 text-xs transition-colors ${
                isActive ? "text-[var(--color-accent)]" : "text-[var(--color-text-tertiary)]"
              }`
            }
          >
            <item.icon className="w-5 h-5 mb-0.5" />
            <span className="truncate max-w-[56px]">{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

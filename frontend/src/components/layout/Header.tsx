import { useTranslation } from "react-i18next";
import { Menu, LogOut, Sun, Moon, Monitor } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { useUIStore } from "../../store/uiStore";
import { useLanguageStore } from "../../store/languageStore";
import { useCountryStore } from "../../store/countryStore";

const languages = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हिन्दी" },
  { code: "te", label: "తెలుగు" },
  { code: "es", label: "ES" },
];

const themeOptions = [
  { value: "light" as const, icon: Sun },
  { value: "dark" as const, icon: Moon },
  { value: "system" as const, icon: Monitor },
];

export function Header() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { toggleSidebar, theme, setTheme } = useUIStore();
  const { language, setLanguage } = useLanguageStore();
  const { country, setCountry } = useCountryStore();

  return (
    <header className="h-16 sticky top-0 z-50 bg-[var(--color-bg-card)] border-b border-[var(--color-border-default)] px-4 flex items-center justify-between transition-colors">
      <div className="flex items-center gap-3">
        <button onClick={toggleSidebar} className="p-2 rounded-lg hover:bg-[var(--color-bg-inset)] md:block hidden transition-colors">
          <Menu className="w-5 h-5 text-[var(--color-text-secondary)]" />
        </button>
        <h1 className="text-lg font-bold text-[var(--color-text-primary)]">{t("app.title")}</h1>
      </div>

      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <div className="flex bg-[var(--color-bg-inset)] rounded-lg p-0.5">
          {themeOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={`p-1.5 rounded-md transition-colors ${
                theme === opt.value
                  ? "bg-[var(--color-bg-card)] text-[var(--color-accent-text)] shadow-sm"
                  : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
              }`}
              title={opt.value}
            >
              <opt.icon className="w-3.5 h-3.5" />
            </button>
          ))}
        </div>

        {/* Country switcher */}
        <div className="flex bg-[var(--color-bg-inset)] rounded-lg p-0.5">
          {(["IN", "US"] as const).map((c) => (
            <button
              key={c}
              onClick={() => setCountry(c)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                country === c
                  ? "bg-[var(--color-bg-card)] text-[var(--color-accent-text)] shadow-sm"
                  : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        {/* Language switcher */}
        <div className="hidden sm:flex bg-[var(--color-bg-inset)] rounded-lg p-0.5">
          {languages.map((lang) => (
            <button
              key={lang.code}
              onClick={() => setLanguage(lang.code)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                language === lang.code
                  ? "bg-[var(--color-bg-card)] text-[var(--color-accent-text)] shadow-sm"
                  : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              {lang.label}
            </button>
          ))}
        </div>

        {/* User avatar / logout */}
        {user && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-[var(--color-accent-subtle)] flex items-center justify-center text-sm font-medium text-[var(--color-accent-text)]">
              {(user.displayName?.[0] || user.email?.[0] || "U").toUpperCase()}
            </div>
            <button onClick={logout} className="p-2 rounded-lg hover:bg-[var(--color-bg-inset)] transition-colors" title={t("nav.logout")}>
              <LogOut className="w-4 h-4 text-[var(--color-text-tertiary)]" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

import { create } from "zustand";

type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

interface UIState {
  sidebarOpen: boolean;
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setTheme: (theme: Theme) => void;
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function resolveTheme(theme: Theme): ResolvedTheme {
  return theme === "system" ? getSystemTheme() : theme;
}

function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem("theme") as Theme) || "system";
}

const initialTheme = getStoredTheme();

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: initialTheme,
  resolvedTheme: resolveTheme(initialTheme),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setTheme: (theme) => {
    localStorage.setItem("theme", theme);
    set({ theme, resolvedTheme: resolveTheme(theme) });
  },
}));

// Listen for system theme changes
if (typeof window !== "undefined") {
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      const { theme } = useUIStore.getState();
      if (theme === "system") {
        useUIStore.setState({ resolvedTheme: getSystemTheme() });
      }
    });
}

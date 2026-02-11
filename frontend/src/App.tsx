import { lazy, Suspense, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LayoutDashboard, Bot, Store, ArrowLeftRight, Trophy, BarChart3, BookOpen } from "lucide-react";
import Shell from "./components/Shell";
import TabNav, { type Tab } from "./components/TabNav";
import { ToastProvider } from "./components/Toast";
import DashboardPage from "./pages/DashboardPage";
import AgentsPage from "./pages/AgentsPage";
import ListingsPage from "./pages/ListingsPage";
import TransactionsPage from "./pages/TransactionsPage";
import ReputationPage from "./pages/ReputationPage";

const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const CatalogPage = lazy(() => import("./pages/CatalogPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

type TabId = "dashboard" | "agents" | "listings" | "catalog" | "transactions" | "analytics" | "reputation";

const TABS: Tab[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "listings", label: "Discover", icon: Store },
  { id: "catalog", label: "Catalog", icon: BookOpen },
  { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "reputation", label: "Reputation", icon: Trophy },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Shell>
          <TabNav tabs={TABS} activeTab={activeTab} onTabChange={(id) => setActiveTab(id as TabId)} />
          <main className="dot-grid-bg mx-auto max-w-7xl px-6 py-6">
            {activeTab === "dashboard" && <DashboardPage onNavigate={(t) => setActiveTab(t as TabId)} />}
            {activeTab === "agents" && <AgentsPage />}
            {activeTab === "listings" && <ListingsPage />}
            {activeTab === "catalog" && (
              <Suspense fallback={<div className="text-text-muted">Loading...</div>}>
                <CatalogPage />
              </Suspense>
            )}
            {activeTab === "transactions" && <TransactionsPage />}
            {activeTab === "analytics" && (
              <Suspense fallback={<div className="text-text-muted">Loading...</div>}>
                <AnalyticsPage />
              </Suspense>
            )}
            {activeTab === "reputation" && <ReputationPage />}
          </main>
        </Shell>
      </ToastProvider>
    </QueryClientProvider>
  );
}

import { lazy, Suspense, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LayoutDashboard, Bot, Store, ArrowLeftRight, Trophy, BarChart3, BookOpen, Wallet, Plug, User, Gift } from "lucide-react";
import Shell from "./components/Shell";
import TabNav, { type Tab } from "./components/TabNav";
import { ToastProvider } from "./components/Toast";
import DashboardPage from "./pages/DashboardPage";
import AgentsPage from "./pages/AgentsPage";
import ListingsPage from "./pages/ListingsPage";
import TransactionsPage from "./pages/TransactionsPage";
import ReputationPage from "./pages/ReputationPage";
import { useCreatorAuth } from "./hooks/useCreatorAuth";

const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const CatalogPage = lazy(() => import("./pages/CatalogPage"));
const WalletPage = lazy(() => import("./pages/WalletPage"));
const IntegrationsPage = lazy(() => import("./pages/IntegrationsPage"));
const CreatorLoginPage = lazy(() => import("./pages/CreatorLoginPage"));
const CreatorDashboardPage = lazy(() => import("./pages/CreatorDashboardPage"));
const RedemptionPage = lazy(() => import("./pages/RedemptionPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

type TabId = "dashboard" | "agents" | "listings" | "catalog" | "transactions" | "wallet" | "analytics" | "reputation" | "integrations" | "creator" | "redeem";

const TABS: Tab[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "listings", label: "Discover", icon: Store },
  { id: "catalog", label: "Catalog", icon: BookOpen },
  { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { id: "wallet", label: "Wallet", icon: Wallet },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "reputation", label: "Reputation", icon: Trophy },
  { id: "integrations", label: "Integrations", icon: Plug },
  { id: "creator", label: "Creator", icon: User },
  { id: "redeem", label: "Redeem", icon: Gift },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const creatorAuth = useCreatorAuth();

  const loading = <div className="text-text-muted">Loading...</div>;

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
              <Suspense fallback={loading}><CatalogPage /></Suspense>
            )}
            {activeTab === "transactions" && <TransactionsPage />}
            {activeTab === "wallet" && (
              <Suspense fallback={loading}><WalletPage /></Suspense>
            )}
            {activeTab === "analytics" && (
              <Suspense fallback={loading}><AnalyticsPage /></Suspense>
            )}
            {activeTab === "reputation" && <ReputationPage />}
            {activeTab === "integrations" && (
              <Suspense fallback={loading}><IntegrationsPage /></Suspense>
            )}
            {activeTab === "creator" && (
              <Suspense fallback={loading}>
                {creatorAuth.isAuthenticated ? (
                  <CreatorDashboardPage
                    token={creatorAuth.token!}
                    creatorName={creatorAuth.creator?.display_name || "Creator"}
                    onNavigate={(t) => setActiveTab(t as TabId)}
                    onLogout={creatorAuth.logout}
                  />
                ) : (
                  <CreatorLoginPage
                    onLogin={creatorAuth.login}
                    onRegister={creatorAuth.register}
                    loading={creatorAuth.loading}
                    error={creatorAuth.error}
                  />
                )}
              </Suspense>
            )}
            {activeTab === "redeem" && (
              <Suspense fallback={loading}>
                {creatorAuth.isAuthenticated ? (
                  <RedemptionPage token={creatorAuth.token!} />
                ) : (
                  <CreatorLoginPage
                    onLogin={creatorAuth.login}
                    onRegister={creatorAuth.register}
                    loading={creatorAuth.loading}
                    error={creatorAuth.error}
                  />
                )}
              </Suspense>
            )}
          </main>
        </Shell>
      </ToastProvider>
    </QueryClientProvider>
  );
}

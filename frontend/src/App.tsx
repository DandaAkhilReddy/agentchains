import { lazy, Suspense, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Shell from "./components/Shell";
import Sidebar, { type TabId } from "./components/Sidebar";
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
const PipelinePage = lazy(() => import("./pages/PipelinePage"));
const DocsPage = lazy(() => import("./pages/DocsPage"));
const TechnologyPage = lazy(() => import("./pages/TechnologyPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const creatorAuth = useCreatorAuth();

  const loading = (
    <div className="flex items-center justify-center py-20 text-text-muted">Loading...</div>
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <div className="flex min-h-screen">
          <Sidebar
            activeTab={activeTab}
            onTabChange={setActiveTab}
            mobileOpen={mobileMenuOpen}
            onMobileClose={() => setMobileMenuOpen(false)}
          />
          <div className="flex-1 transition-all duration-300 sidebar-offset">
            <Shell onMenuToggle={() => setMobileMenuOpen((o) => !o)}>
              <main className="dot-grid-bg px-4 py-4 md:px-6 md:py-6 animate-slide-up">
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
                {activeTab === "pipeline" && (
                  <Suspense fallback={loading}><PipelinePage /></Suspense>
                )}
                {activeTab === "docs" && (
                  <Suspense fallback={loading}><DocsPage /></Suspense>
                )}
                {activeTab === "technology" && (
                  <Suspense fallback={loading}><TechnologyPage /></Suspense>
                )}
              </main>
            </Shell>
          </div>
        </div>
      </ToastProvider>
    </QueryClientProvider>
  );
}

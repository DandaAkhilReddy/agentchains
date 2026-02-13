import React, { lazy, Suspense, useState } from "react";
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

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: "center", color: "#e2e8f0", background: "#0a0e1a", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <h1 style={{ fontSize: 24, marginBottom: 16 }}>Something went wrong</h1>
          <p style={{ color: "#94a3b8", marginBottom: 24 }}>{this.state.error?.message}</p>
          <button onClick={() => window.location.reload()} style={{ padding: "8px 24px", background: "#60a5fa", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const creatorAuth = useCreatorAuth();

  const loading = (
    <div className="flex items-center justify-center py-20" style={{ color: '#64748b' }}>Loading...</div>
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
      <ToastProvider>
        <div className="flex min-h-screen" style={{ backgroundColor: '#0a0e1a' }}>
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
                        onLogin={async (email, password) => { await creatorAuth.login(email, password); }}
                        onRegister={async (data) => { await creatorAuth.register(data); }}
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
                        onLogin={async (email, password) => { await creatorAuth.login(email, password); }}
                        onRegister={async (data) => { await creatorAuth.register(data); }}
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
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

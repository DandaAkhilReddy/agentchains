import { lazy, Suspense, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { LoadingSpinner } from "./components/shared/LoadingSpinner";
import { ErrorBoundary } from "./components/shared/ErrorBoundary";
import { useUIStore } from "./store/uiStore";

// Code-split pages for <170KB critical path
const LoginPage = lazy(() => import("./components/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const LoansPage = lazy(() => import("./pages/LoansPage").then((m) => ({ default: m.LoansPage })));
const LoanDetailPage = lazy(() => import("./pages/LoanDetailPage").then((m) => ({ default: m.LoanDetailPage })));
const ScanDocumentPage = lazy(() => import("./pages/ScanDocumentPage").then((m) => ({ default: m.ScanDocumentPage })));
const OptimizerPage = lazy(() => import("./pages/OptimizerPage").then((m) => ({ default: m.OptimizerPage })));
const EMICalculatorPage = lazy(() => import("./pages/EMICalculatorPage").then((m) => ({ default: m.EMICalculatorPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const FeedbackPage = lazy(() => import("./pages/FeedbackPage").then((m) => ({ default: m.FeedbackPage })));
const AdminDashboardPage = lazy(() => import("./pages/AdminDashboardPage").then((m) => ({ default: m.AdminDashboardPage })));

function PageLoader() {
  return <LoadingSpinner size="lg" />;
}

export default function App() {
  useAuth();

  const resolvedTheme = useUIStore((s) => s.resolvedTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
    document.documentElement.style.colorScheme = resolvedTheme;
  }, [resolvedTheme]);

  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/emi-calculator" element={<EMICalculatorPage />} />

          {/* Protected routes with AppShell layout */}
          <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/loans" element={<LoansPage />} />
            <Route path="/loans/:id" element={<LoanDetailPage />} />
            <Route path="/scanner" element={<ScanDocumentPage />} />
            <Route path="/optimizer" element={<OptimizerPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/feedback" element={<FeedbackPage />} />
            <Route path="/admin" element={<AdminDashboardPage />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}

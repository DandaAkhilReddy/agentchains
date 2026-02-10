import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Shell from "./components/Shell";
import TabNav, { type Tab } from "./components/TabNav";
import DashboardPage from "./pages/DashboardPage";
import AgentsPage from "./pages/AgentsPage";
import ListingsPage from "./pages/ListingsPage";
import TransactionsPage from "./pages/TransactionsPage";
import ReputationPage from "./pages/ReputationPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

type TabId = "dashboard" | "agents" | "listings" | "transactions" | "reputation";

const TABS: Tab[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "agents", label: "Agents" },
  { id: "listings", label: "Discover" },
  { id: "transactions", label: "Transactions" },
  { id: "reputation", label: "Reputation" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");

  return (
    <QueryClientProvider client={queryClient}>
      <Shell>
        <TabNav tabs={TABS} activeTab={activeTab} onTabChange={(id) => setActiveTab(id as TabId)} />
        <main className="mx-auto max-w-7xl px-6 py-6">
          {activeTab === "dashboard" && <DashboardPage />}
          {activeTab === "agents" && <AgentsPage />}
          {activeTab === "listings" && <ListingsPage />}
          {activeTab === "transactions" && <TransactionsPage />}
          {activeTab === "reputation" && <ReputationPage />}
        </main>
      </Shell>
    </QueryClientProvider>
  );
}

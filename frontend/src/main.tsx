import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ToastContainer } from "./components/shared/ToastContainer";
import { OfflineBanner } from "./components/shared/OfflineBanner";
import "./index.css";
import "./lib/suppress-locize"; // Must be before i18n — patches console.log before i18next captures it
import "./lib/i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <OfflineBanner />
        <App />
        <ToastContainer />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);

import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileNav } from "./MobileNav";
import { ChatBot } from "../chat/ChatBot";
import { useUIStore } from "../../store/uiStore";

export function AppShell() {
  const { sidebarOpen } = useUIStore();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-[var(--color-bg-app)] transition-colors">
      <Header />
      <div className="flex">
        {/* Desktop sidebar */}
        <div className={`hidden md:block transition-all duration-300 ease-out overflow-hidden ${sidebarOpen ? "w-64" : "w-0"}`}>
          <Sidebar />
        </div>
        {/* Main content */}
        <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">
          <div key={location.pathname} className="animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
      {/* Mobile bottom nav */}
      <MobileNav />
      {/* AI Chatbot */}
      <ChatBot />
    </div>
  );
}

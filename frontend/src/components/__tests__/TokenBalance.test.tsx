import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TokenBalance from "../TokenBalance";
import * as useAuthModule from "../../hooks/useAuth";
import * as apiModule from "../../lib/api";
import type { WalletBalanceResponse } from "../../types/api";

// Mock the hooks and API
vi.mock("../../hooks/useAuth");
vi.mock("../../lib/api");

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

function mockBalance(balance: number): WalletBalanceResponse {
  return {
    balance,
    total_earned: 0,
    total_spent: 0,
    total_deposited: balance,
    total_fees_paid: 0,
  };
}

describe("TokenBalance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders USD amount with formatUSD formatting for small balance", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(123.45));

    const { container } = render(<TokenBalance />, { wrapper: createWrapper() });

    // Wait for query to resolve
    await vi.waitFor(() => {
      // formatUSD(123.45) -> "$123.45"
      expect(screen.getByText("$123.45")).toBeInTheDocument();
    });

    // Check that Wallet icon is present
    const walletIcon = container.querySelector("svg");
    expect(walletIcon).toBeInTheDocument();
  });

  test("renders USD amount with K suffix for thousands", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(5432.1));

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(5432.1) -> "$5.4K"
      expect(screen.getByText("$5.4K")).toBeInTheDocument();
    });
  });

  test("renders USD amount with M suffix for millions", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(2500000));

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(2500000) -> "$2.5M"
      expect(screen.getByText("$2.5M")).toBeInTheDocument();
    });
  });

  test("handles zero balance correctly", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(0));

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(0) -> "$0.00"
      expect(screen.getByText("$0.00")).toBeInTheDocument();
    });
  });

  test("handles large numbers with millions formatting", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(15750000));

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(15750000) -> "$15.8M"
      expect(screen.getByText("$15.8M")).toBeInTheDocument();
    });
  });

  test("displays USD formatted balance", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(999.99));

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(999.99) -> "$999.99"
      const balanceText = screen.getByText("$999.99");
      expect(balanceText).toBeInTheDocument();
      expect(balanceText.textContent).toContain("$");
    });
  });

  test("returns null when token is not present", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: "",
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: false,
    });

    const { container } = render(<TokenBalance />, { wrapper: createWrapper() });

    // Component should render nothing
    expect(container.firstChild).toBeNull();
  });

  test("returns null when data is not yet loaded", () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    // Don't resolve the promise immediately
    vi.spyOn(apiModule, "fetchWalletBalance").mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    const { container } = render(<TokenBalance />, { wrapper: createWrapper() });

    // Component should render nothing while loading
    expect(container.firstChild).toBeNull();
  });

  test("applies monospace font to balance", async () => {
    const mockToken = "test-token";

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockBalance(500));

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(500) -> "$500.00"
      const balanceElement = screen.getByText("$500.00");
      expect(balanceElement).toHaveStyle({ fontFamily: "var(--font-mono)" });
    });
  });
});

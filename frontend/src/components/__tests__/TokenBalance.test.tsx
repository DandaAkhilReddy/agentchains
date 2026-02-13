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

describe("TokenBalance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders USD amount with formatUSD formatting for small balance", async () => {
    const mockToken = "test-token";
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 123.45,
        total_deposited: 200,
        total_earned: 50,
        total_spent: 126.55,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

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
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 5432.1,
        total_deposited: 10000,
        total_earned: 0,
        total_spent: 4567.9,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(5432.1) -> "$5.4K"
      expect(screen.getByText("$5.4K")).toBeInTheDocument();
    });
  });

  test("renders USD amount with M suffix for millions", async () => {
    const mockToken = "test-token";
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 2500000,
        total_deposited: 3000000,
        total_earned: 0,
        total_spent: 500000,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(2500000) -> "$2.5M"
      expect(screen.getByText("$2.5M")).toBeInTheDocument();
    });
  });

  test("handles zero balance correctly", async () => {
    const mockToken = "test-token";
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 0,
        total_deposited: 0,
        total_earned: 0,
        total_spent: 0,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(0) -> "$0.00"
      expect(screen.getByText("$0.00")).toBeInTheDocument();
    });
  });

  test("handles large numbers with millions formatting", async () => {
    const mockToken = "test-token";
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 15750000,
        total_deposited: 20000000,
        total_earned: 0,
        total_spent: 4250000,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(15750000) -> "$15.8M"
      expect(screen.getByText("$15.8M")).toBeInTheDocument();
    });
  });

  test("displays USD formatted balance", async () => {
    const mockToken = "test-token";
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 999.99,
        total_deposited: 1000,
        total_earned: 0,
        total_spent: 0.01,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

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
    const mockData: WalletBalanceResponse = {
      account: {
        id: "acc-1",
        agent_id: null,
        balance: 500,
        total_deposited: 500,
        total_earned: 0,
        total_spent: 0,
        total_fees_paid: 0,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };

    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      token: mockToken,
      login: vi.fn(),
      logout: vi.fn(),
      isAuthenticated: true,
    });

    vi.spyOn(apiModule, "fetchWalletBalance").mockResolvedValue(mockData);

    render(<TokenBalance />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // formatUSD(500) -> "$500.00"
      const balanceElement = screen.getByText("$500.00");
      expect(balanceElement).toHaveStyle({ fontFamily: "var(--font-mono)" });
    });
  });
});

import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useCreatorAuth } from "../useCreatorAuth";
import * as api from "../../lib/api";

// Mock the API module
vi.mock("../../lib/api", () => ({
  creatorLogin: vi.fn(),
  creatorRegister: vi.fn(),
}));

describe("useCreatorAuth", () => {
  let localStorageMock: Record<string, string>;

  beforeEach(() => {
    // Mock localStorage
    localStorageMock = {};

    global.localStorage = {
      getItem: vi.fn((key: string) => localStorageMock[key] || null),
      setItem: vi.fn((key: string, value: string) => {
        localStorageMock[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete localStorageMock[key];
      }),
      clear: vi.fn(() => {
        localStorageMock = {};
      }),
      length: 0,
      key: vi.fn(),
    } as Storage;

    // Reset mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Initial state", () => {
    test("returns null token when localStorage is empty", () => {
      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.token).toBeNull();
      expect(result.current.creator).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    test("loads token from localStorage on initialization", () => {
      localStorageMock["agentchains_creator_jwt"] = "test-token-123";

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.token).toBe("test-token-123");
      expect(result.current.isAuthenticated).toBe(true);
    });

    test("loads creator from localStorage JSON on initialization", () => {
      const mockCreator = {
        id: "creator-123",
        email: "test@example.com",
        display_name: "Test Creator",
        payout_method: "upi",
        status: "active",
      };

      localStorageMock["agentchains_creator_jwt"] = "test-token";
      localStorageMock["agentchains_creator"] = JSON.stringify(mockCreator);

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.creator).toEqual(mockCreator);
      expect(result.current.token).toBe("test-token");
      expect(result.current.isAuthenticated).toBe(true);
    });

    test("handles corrupted localStorage JSON gracefully", () => {
      localStorageMock["agentchains_creator"] = "{ invalid json }";

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.creator).toBeNull();
      expect(result.current.error).toBeNull();
    });

    test("handles localStorage access errors gracefully", () => {
      global.localStorage.getItem = vi.fn(() => {
        throw new Error("Storage access denied");
      });

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.token).toBeNull();
      expect(result.current.creator).toBeNull();
    });
  });

  describe("login()", () => {
    test("calls creatorLogin API and stores token+creator on success", async () => {
      const mockResponse = {
        token: "new-token-456",
        creator: {
          id: "creator-456",
          email: "user@test.com",
          display_name: "New User",
          payout_method: "bank",
          status: "active",
        },
      };

      vi.mocked(api.creatorLogin).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.loading).toBe(false);

      await act(async () => {
        const response = await result.current.login("user@test.com", "password123");
        expect(response).toEqual(mockResponse);
      });

      expect(api.creatorLogin).toHaveBeenCalledWith({
        email: "user@test.com",
        password: "password123",
      });
      expect(result.current.token).toBe("new-token-456");
      expect(result.current.creator).toEqual(mockResponse.creator);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();

      expect(localStorage.setItem).toHaveBeenCalledWith(
        "agentchains_creator_jwt",
        "new-token-456"
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        "agentchains_creator",
        JSON.stringify(mockResponse.creator)
      );
    });

    test("sets loading to true during login", async () => {
      const mockResponse = {
        token: "token",
        creator: {
          id: "id",
          email: "test@test.com",
          display_name: "Test",
          payout_method: "none",
          status: "active",
        },
      };

      let resolveLogin: (value: any) => void;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });

      vi.mocked(api.creatorLogin).mockReturnValueOnce(loginPromise as any);

      const { result } = renderHook(() => useCreatorAuth());

      act(() => {
        result.current.login("test@test.com", "password");
      });

      expect(result.current.loading).toBe(true);

      await act(async () => {
        resolveLogin!(mockResponse);
        await loginPromise;
      });

      expect(result.current.loading).toBe(false);
    });

    test("sets error on login failure", async () => {
      const errorMessage = "Invalid credentials";
      vi.mocked(api.creatorLogin).mockRejectedValueOnce(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCreatorAuth());

      await act(async () => {
        try {
          await result.current.login("wrong@test.com", "wrongpass");
        } catch (e) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe(errorMessage);
      expect(result.current.token).toBeNull();
      expect(result.current.creator).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.loading).toBe(false);
    });

    test("handles login failure without error message", async () => {
      vi.mocked(api.creatorLogin).mockRejectedValueOnce({});

      const { result } = renderHook(() => useCreatorAuth());

      await act(async () => {
        try {
          await result.current.login("test@test.com", "pass");
        } catch (e) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe("Login failed");
    });
  });

  describe("register()", () => {
    test("calls creatorRegister API and stores token+creator on success", async () => {
      const mockResponse = {
        token: "registered-token-789",
        creator: {
          id: "creator-789",
          email: "newuser@test.com",
          display_name: "New Creator",
          payout_method: "upi",
          status: "pending_verification",
        },
      };

      vi.mocked(api.creatorRegister).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useCreatorAuth());

      const registerData = {
        email: "newuser@test.com",
        password: "securepass123",
        display_name: "New Creator",
        phone: "+919876543210",
        country: "IN",
      };

      await act(async () => {
        const response = await result.current.register(registerData);
        expect(response).toEqual(mockResponse);
      });

      expect(api.creatorRegister).toHaveBeenCalledWith(registerData);
      expect(result.current.token).toBe("registered-token-789");
      expect(result.current.creator).toEqual(mockResponse.creator);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();

      expect(localStorage.setItem).toHaveBeenCalledWith(
        "agentchains_creator_jwt",
        "registered-token-789"
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        "agentchains_creator",
        JSON.stringify(mockResponse.creator)
      );
    });

    test("sets loading to true during registration", async () => {
      const mockResponse = {
        token: "token",
        creator: {
          id: "id",
          email: "test@test.com",
          display_name: "Test",
          payout_method: "none",
          status: "active",
        },
      };

      let resolveRegister: (value: any) => void;
      const registerPromise = new Promise((resolve) => {
        resolveRegister = resolve;
      });

      vi.mocked(api.creatorRegister).mockReturnValueOnce(
        registerPromise as any
      );

      const { result } = renderHook(() => useCreatorAuth());

      act(() => {
        result.current.register({
          email: "test@test.com",
          password: "password",
          display_name: "Test",
        });
      });

      expect(result.current.loading).toBe(true);

      await act(async () => {
        resolveRegister!(mockResponse);
        await registerPromise;
      });

      expect(result.current.loading).toBe(false);
    });

    test("sets error on registration failure", async () => {
      const errorMessage = "Email already exists";
      vi.mocked(api.creatorRegister).mockRejectedValueOnce(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCreatorAuth());

      await act(async () => {
        try {
          await result.current.register({
            email: "existing@test.com",
            password: "pass",
            display_name: "Test",
          });
        } catch (e) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe(errorMessage);
      expect(result.current.token).toBeNull();
      expect(result.current.creator).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.loading).toBe(false);
    });

    test("handles registration failure without error message", async () => {
      vi.mocked(api.creatorRegister).mockRejectedValueOnce({});

      const { result } = renderHook(() => useCreatorAuth());

      await act(async () => {
        try {
          await result.current.register({
            email: "test@test.com",
            password: "pass",
            display_name: "Test",
          });
        } catch (e) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe("Registration failed");
    });
  });

  describe("logout()", () => {
    test("clears all state and removes from localStorage", () => {
      const mockCreator = {
        id: "creator-123",
        email: "test@example.com",
        display_name: "Test Creator",
        payout_method: "upi",
        status: "active",
      };

      localStorageMock["agentchains_creator_jwt"] = "test-token";
      localStorageMock["agentchains_creator"] = JSON.stringify(mockCreator);

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.token).toBe("test-token");
      expect(result.current.creator).toEqual(mockCreator);
      expect(result.current.isAuthenticated).toBe(true);

      act(() => {
        result.current.logout();
      });

      expect(result.current.token).toBeNull();
      expect(result.current.creator).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);

      expect(localStorage.removeItem).toHaveBeenCalledWith(
        "agentchains_creator_jwt"
      );
      expect(localStorage.removeItem).toHaveBeenCalledWith(
        "agentchains_creator"
      );
    });

    test("logout works when already logged out", () => {
      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.token).toBeNull();

      act(() => {
        result.current.logout();
      });

      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe("isAuthenticated", () => {
    test("returns true when token exists", () => {
      localStorageMock["agentchains_creator_jwt"] = "valid-token";

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.isAuthenticated).toBe(true);
    });

    test("returns false when token is null", () => {
      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.isAuthenticated).toBe(false);
    });

    test("updates to true after successful login", async () => {
      const mockResponse = {
        token: "new-token",
        creator: {
          id: "creator-id",
          email: "test@test.com",
          display_name: "Test",
          payout_method: "none",
          status: "active",
        },
      };

      vi.mocked(api.creatorLogin).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.isAuthenticated).toBe(false);

      await act(async () => {
        await result.current.login("test@test.com", "password");
      });

      expect(result.current.isAuthenticated).toBe(true);
    });

    test("updates to false after logout", () => {
      localStorageMock["agentchains_creator_jwt"] = "token";

      const { result } = renderHook(() => useCreatorAuth());

      expect(result.current.isAuthenticated).toBe(true);

      act(() => {
        result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe("error handling", () => {
    test("clears error on successful login after previous error", async () => {
      vi.mocked(api.creatorLogin)
        .mockRejectedValueOnce(new Error("First error"))
        .mockResolvedValueOnce({
          token: "token",
          creator: {
            id: "id",
            email: "test@test.com",
            display_name: "Test",
            payout_method: "none",
            status: "active",
          },
        });

      const { result } = renderHook(() => useCreatorAuth());

      // First login fails
      await act(async () => {
        try {
          await result.current.login("test@test.com", "wrong");
        } catch (e) {
          // Expected
        }
      });

      expect(result.current.error).toBe("First error");

      // Second login succeeds
      await act(async () => {
        await result.current.login("test@test.com", "correct");
      });

      expect(result.current.error).toBeNull();
      expect(result.current.isAuthenticated).toBe(true);
    });

    test("clears error on successful registration after previous error", async () => {
      vi.mocked(api.creatorRegister)
        .mockRejectedValueOnce(new Error("Registration error"))
        .mockResolvedValueOnce({
          token: "token",
          creator: {
            id: "id",
            email: "test@test.com",
            display_name: "Test",
            payout_method: "none",
            status: "active",
          },
        });

      const { result } = renderHook(() => useCreatorAuth());

      // First registration fails
      await act(async () => {
        try {
          await result.current.register({
            email: "test@test.com",
            password: "pass",
            display_name: "Test",
          });
        } catch (e) {
          // Expected
        }
      });

      expect(result.current.error).toBe("Registration error");

      // Second registration succeeds
      await act(async () => {
        await result.current.register({
          email: "test@test.com",
          password: "pass",
          display_name: "Test",
        });
      });

      expect(result.current.error).toBeNull();
      expect(result.current.isAuthenticated).toBe(true);
    });
  });
});

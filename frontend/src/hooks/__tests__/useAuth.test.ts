import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAuth } from "../useAuth";

describe("useAuth", () => {
  let localStorageMock: Record<string, string>;

  beforeEach(() => {
    // Create a fresh localStorage mock for each test
    localStorageMock = {};

    // Mock localStorage methods
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => localStorageMock[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        localStorageMock[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete localStorageMock[key];
      }),
      clear: vi.fn(() => {
        localStorageMock = {};
      }),
    });
  });

  it("should initialize with empty token when localStorage is empty", () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current.token).toBe("");
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.getItem).toHaveBeenCalledWith("agent_jwt");
  });

  it("should initialize with token from localStorage if present", () => {
    localStorageMock["agent_jwt"] = "existing-token-123";

    const { result } = renderHook(() => useAuth());

    expect(result.current.token).toBe("existing-token-123");
    expect(result.current.isAuthenticated).toBe(true);
    expect(localStorage.getItem).toHaveBeenCalledWith("agent_jwt");
  });

  it("should set token state and persist to localStorage on login", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.login("new-token-456");
    });

    expect(result.current.token).toBe("new-token-456");
    expect(result.current.isAuthenticated).toBe(true);
    expect(localStorage.setItem).toHaveBeenCalledWith("agent_jwt", "new-token-456");
    expect(localStorageMock["agent_jwt"]).toBe("new-token-456");
  });

  it("should clear token state and remove from localStorage on logout", () => {
    localStorageMock["agent_jwt"] = "token-to-clear";
    const { result } = renderHook(() => useAuth());

    expect(result.current.token).toBe("token-to-clear");

    act(() => {
      result.current.logout();
    });

    expect(result.current.token).toBe("");
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.removeItem).toHaveBeenCalledWith("agent_jwt");
    expect(localStorageMock["agent_jwt"]).toBeUndefined();
  });

  it("should return isAuthenticated as true when token is non-empty", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.login("valid-token");
    });

    expect(result.current.isAuthenticated).toBe(true);
  });

  it("should return isAuthenticated as false when token is empty", () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current.isAuthenticated).toBe(false);

    // Also test after logout
    act(() => {
      result.current.login("temp-token");
    });

    expect(result.current.isAuthenticated).toBe(true);

    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
  });

  it("should clear token after login then logout", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.login("temporary-token");
    });

    expect(result.current.token).toBe("temporary-token");
    expect(result.current.isAuthenticated).toBe(true);
    expect(localStorageMock["agent_jwt"]).toBe("temporary-token");

    act(() => {
      result.current.logout();
    });

    expect(result.current.token).toBe("");
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorageMock["agent_jwt"]).toBeUndefined();
  });

  it("should replace token with last login when multiple logins occur", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.login("first-token");
    });

    expect(result.current.token).toBe("first-token");
    expect(localStorageMock["agent_jwt"]).toBe("first-token");

    act(() => {
      result.current.login("second-token");
    });

    expect(result.current.token).toBe("second-token");
    expect(localStorageMock["agent_jwt"]).toBe("second-token");

    act(() => {
      result.current.login("third-token");
    });

    expect(result.current.token).toBe("third-token");
    expect(result.current.isAuthenticated).toBe(true);
    expect(localStorageMock["agent_jwt"]).toBe("third-token");
  });

  it("should maintain stable function references (login and logout)", () => {
    const { result, rerender } = renderHook(() => useAuth());

    const initialLogin = result.current.login;
    const initialLogout = result.current.logout;

    // Trigger a re-render by calling login
    act(() => {
      result.current.login("test-token");
    });

    rerender();

    // Function references should remain the same due to useCallback
    expect(result.current.login).toBe(initialLogin);
    expect(result.current.logout).toBe(initialLogout);
  });

  it("should handle empty string token as unauthenticated", () => {
    const { result } = renderHook(() => useAuth());

    act(() => {
      result.current.login("");
    });

    expect(result.current.token).toBe("");
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorageMock["agent_jwt"]).toBe("");
  });
});

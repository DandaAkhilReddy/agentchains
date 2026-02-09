/// <reference types="vitest/globals" />
import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { useAuth } from "../hooks/useAuth";
import { useAuthStore } from "../store/authStore";

// Auth is paused — useAuth just sets a fake user and returns no-op functions

describe("useAuth (auth paused)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, loading: true });
  });

  it("sets fake admin user on mount", async () => {
    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.user).toBeTruthy();
      expect((result.current.user as any).uid).toBe("dev-admin");
      expect((result.current.user as any).email).toBe("admin@test.com");
      expect((result.current.user as any).displayName).toBe("Admin");
    });
  });

  it("sets loading to false on mount", async () => {
    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it("returns loginWithGoogle as a no-op function", async () => {
    const { result } = renderHook(() => useAuth());
    await act(async () => {
      await result.current.loginWithGoogle();
    });
    // Should not throw
  });

  it("returns loginWithEmail as a no-op function", async () => {
    const { result } = renderHook(() => useAuth());
    await act(async () => {
      await result.current.loginWithEmail("test@example.com", "password123");
    });
    // Should not throw
  });

  it("returns signupWithEmail as a no-op function", async () => {
    const { result } = renderHook(() => useAuth());
    await act(async () => {
      await result.current.signupWithEmail("test@example.com", "password123", "Test");
    });
    // Should not throw
  });

  it("returns resetPassword as a no-op function", async () => {
    const { result } = renderHook(() => useAuth());
    await act(async () => {
      await result.current.resetPassword("test@example.com");
    });
    // Should not throw
  });

  it("returns logout as a no-op function", async () => {
    const { result } = renderHook(() => useAuth());
    await act(async () => {
      await result.current.logout();
    });
    // Should not throw
  });
});

/// <reference types="vitest/globals" />
import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { useAuth } from "../hooks/useAuth";
import { useAuthStore } from "../store/authStore";
import type { User } from "firebase/auth";

// Mock modules
vi.mock("../lib/firebase", () => ({
  auth: { signOut: vi.fn() },
  signInWithPopup: vi.fn(),
  googleProvider: {},
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  default: { post: vi.fn() },
}));

import {
  auth,
  signInWithPopup,
  googleProvider,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile,
} from "../lib/firebase";
import { onAuthStateChanged } from "firebase/auth";
import api from "../lib/api";

describe("useAuth", () => {
  const mockUser = {
    uid: "test-uid",
    email: "test@example.com",
    displayName: "Test User",
    getIdToken: vi.fn().mockResolvedValue("mock-token"),
  } as unknown as User;

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, loading: true });
    vi.mocked(onAuthStateChanged).mockImplementation(() => vi.fn());
  });

  describe("onAuthStateChanged", () => {
    it("sets user and stops loading when auth state changes", async () => {
      vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback: any) => {
        setTimeout(() => callback(mockUser), 0);
        return vi.fn();
      });
      vi.mocked(api.post).mockResolvedValue({ data: {} });

      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.loading).toBe(false);
      });
    });

    it("verifies token when user is authenticated", async () => {
      vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback: any) => {
        setTimeout(() => callback(mockUser), 0);
        return vi.fn();
      });
      vi.mocked(api.post).mockResolvedValue({ data: {} });

      renderHook(() => useAuth());

      await waitFor(() => {
        expect(mockUser.getIdToken).toHaveBeenCalled();
        expect(api.post).toHaveBeenCalledWith("/api/auth/verify-token", null, {
          headers: { Authorization: "Bearer mock-token" },
        });
      });
    });

    it("logs warning when token verification fails", async () => {
      const consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      const error = new Error("Verification failed");

      vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback: any) => {
        setTimeout(() => callback(mockUser), 0);
        return vi.fn();
      });
      vi.mocked(api.post).mockRejectedValue(error);

      renderHook(() => useAuth());

      await waitFor(() => {
        expect(consoleWarnSpy).toHaveBeenCalledWith("Token verification failed:", error);
      });

      consoleWarnSpy.mockRestore();
    });

    it("clears user when auth state is null", async () => {
      vi.mocked(onAuthStateChanged).mockImplementation((_auth, callback: any) => {
        setTimeout(() => callback(null), 0);
        return vi.fn();
      });

      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.loading).toBe(false);
      });
    });
  });

  describe("loginWithGoogle", () => {
    it("calls signInWithPopup with auth and googleProvider", async () => {
      vi.mocked(signInWithPopup).mockResolvedValue({} as any);

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        await result.current.loginWithGoogle();
      });

      expect(signInWithPopup).toHaveBeenCalledWith(auth, googleProvider);
    });

    it("stops loading even if signInWithPopup fails", async () => {
      vi.mocked(signInWithPopup).mockRejectedValue(new Error("Login failed"));

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        try {
          await result.current.loginWithGoogle();
        } catch {
          // Expected
        }
      });

      expect(result.current.loading).toBe(false);
    });
  });

  describe("loginWithEmail", () => {
    it("calls signInWithEmailAndPassword with correct parameters", async () => {
      vi.mocked(signInWithEmailAndPassword).mockResolvedValue({} as any);

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        await result.current.loginWithEmail("test@example.com", "password123");
      });

      expect(signInWithEmailAndPassword).toHaveBeenCalledWith(
        auth,
        "test@example.com",
        "password123"
      );
    });

    it("stops loading even if signInWithEmailAndPassword fails", async () => {
      vi.mocked(signInWithEmailAndPassword).mockRejectedValue(new Error("Invalid"));

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        try {
          await result.current.loginWithEmail("test@example.com", "wrong");
        } catch {
          // Expected
        }
      });

      expect(result.current.loading).toBe(false);
    });
  });

  describe("signupWithEmail", () => {
    it("calls createUserWithEmailAndPassword and updateProfile", async () => {
      const newUser = { uid: "new-uid" } as User;
      vi.mocked(createUserWithEmailAndPassword).mockResolvedValue({ user: newUser } as any);
      vi.mocked(updateProfile).mockResolvedValue(undefined);

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        await result.current.signupWithEmail("new@example.com", "password123", "New User");
      });

      expect(createUserWithEmailAndPassword).toHaveBeenCalledWith(auth, "new@example.com", "password123");
      expect(updateProfile).toHaveBeenCalledWith(newUser, { displayName: "New User" });
    });

    it("stops loading even if signup fails", async () => {
      vi.mocked(createUserWithEmailAndPassword).mockRejectedValue(new Error("Email in use"));

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        try {
          await result.current.signupWithEmail("existing@example.com", "password123", "User");
        } catch {
          // Expected
        }
      });

      expect(result.current.loading).toBe(false);
    });

    it("stops loading even if updateProfile fails", async () => {
      const newUser = { uid: "new-uid" } as User;
      vi.mocked(createUserWithEmailAndPassword).mockResolvedValue({ user: newUser } as any);
      vi.mocked(updateProfile).mockRejectedValue(new Error("Update failed"));

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        try {
          await result.current.signupWithEmail("new@example.com", "password123", "New User");
        } catch {
          // Expected
        }
      });

      expect(result.current.loading).toBe(false);
    });
  });

  describe("resetPassword", () => {
    it("calls sendPasswordResetEmail with correct email", async () => {
      vi.mocked(sendPasswordResetEmail).mockResolvedValue(undefined);

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        await result.current.resetPassword("test@example.com");
      });

      expect(sendPasswordResetEmail).toHaveBeenCalledWith(auth, "test@example.com");
    });

    it("propagates errors from sendPasswordResetEmail", async () => {
      vi.mocked(sendPasswordResetEmail).mockRejectedValue(new Error("Email not found"));

      const { result } = renderHook(() => useAuth());

      await expect(
        act(async () => {
          await result.current.resetPassword("nonexistent@example.com");
        })
      ).rejects.toThrow("Email not found");
    });
  });

  describe("logout", () => {
    it("calls auth.signOut and clears user", async () => {
      vi.mocked(auth.signOut).mockResolvedValue(undefined);
      useAuthStore.setState({ user: mockUser, loading: false });

      const { result } = renderHook(() => useAuth());

      await act(async () => {
        await result.current.logout();
      });

      expect(auth.signOut).toHaveBeenCalled();
      expect(result.current.user).toBeNull();
    });

    it("propagates errors from signOut", async () => {
      vi.mocked(auth.signOut).mockRejectedValue(new Error("Signout failed"));

      const { result } = renderHook(() => useAuth());

      await expect(
        act(async () => {
          await result.current.logout();
        })
      ).rejects.toThrow("Signout failed");
    });
  });

  describe("cleanup", () => {
    it("unsubscribes from onAuthStateChanged on unmount", () => {
      const unsubscribe = vi.fn();
      vi.mocked(onAuthStateChanged).mockReturnValue(unsubscribe);

      const { unmount } = renderHook(() => useAuth());

      expect(unsubscribe).not.toHaveBeenCalled();
      unmount();
      expect(unsubscribe).toHaveBeenCalled();
    });
  });
});

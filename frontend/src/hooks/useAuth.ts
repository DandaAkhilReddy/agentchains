import { useEffect } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import {
  auth,
  signInWithPopup,
  googleProvider,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile,
} from "../lib/firebase";
import { useAuthStore } from "../store/authStore";
import api from "../lib/api";

const BYPASS_AUTH = import.meta.env.VITE_BYPASS_AUTH === "true";

const fakeUser: User = {
  uid: "dev-admin",
  email: "admin@example.com",
  displayName: "Admin",
  emailVerified: true,
  isAnonymous: false,
  metadata: {} as any,
  providerData: [],
  refreshToken: "dev-token",
  tenantId: null,
  delete: async () => {},
  getIdToken: async () => "dev-token",
  getIdTokenResult: async () => ({ token: "dev-token" } as any),
  reload: async () => {},
  toJSON: () => ({}),
  phoneNumber: null,
  photoURL: null,
  providerId: "custom",
};

export function useAuth() {
  const { user, loading, setUser, setLoading } = useAuthStore();

  useEffect(() => {
    if (BYPASS_AUTH) {
      setUser(fakeUser);
      setLoading(false);
      return;
    }
    // Safety net: if Firebase auth hasn't resolved in 5s, stop loading spinner
    const timeout = setTimeout(() => {
      if (useAuthStore.getState().loading) {
        setLoading(false);
      }
    }, 5000);

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      clearTimeout(timeout);
      setUser(firebaseUser);
      if (firebaseUser) {
        try {
          const token = await firebaseUser.getIdToken();
          await api.post("/api/auth/verify-token", null, {
            headers: { Authorization: `Bearer ${token}` },
          });
        } catch (err) {
          console.warn("Token verification failed:", err);
        }
      }
    });

    return () => {
      clearTimeout(timeout);
      unsubscribe();
    };
  }, [setUser, setLoading]);

  const loginWithGoogle = async () => {
    if (BYPASS_AUTH) return;
    setLoading(true);
    try {
      await signInWithPopup(auth, googleProvider);
    } finally {
      setLoading(false);
    }
  };

  const loginWithEmail = async (email: string, password: string) => {
    if (BYPASS_AUTH) return;
    setLoading(true);
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } finally {
      setLoading(false);
    }
  };

  const signupWithEmail = async (email: string, password: string, displayName: string) => {
    if (BYPASS_AUTH) return;
    setLoading(true);
    try {
      const { user: newUser } = await createUserWithEmailAndPassword(auth, email, password);
      await updateProfile(newUser, { displayName });
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async (email: string) => {
    if (BYPASS_AUTH) return;
    await sendPasswordResetEmail(auth, email);
  };

  const logout = async () => {
    if (BYPASS_AUTH) {
      setUser(fakeUser);
      return;
    }
    await auth.signOut();
    setUser(null);
  };

  return { user, loading, loginWithGoogle, loginWithEmail, signupWithEmail, resetPassword, logout };
}

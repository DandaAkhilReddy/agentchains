import { useEffect } from "react";
import { onAuthStateChanged } from "firebase/auth";
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

export function useAuth() {
  const { user, loading, setUser, setLoading } = useAuthStore();

  useEffect(() => {
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
    setLoading(true);
    try {
      await signInWithPopup(auth, googleProvider);
    } finally {
      setLoading(false);
    }
  };

  const loginWithEmail = async (email: string, password: string) => {
    setLoading(true);
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } finally {
      setLoading(false);
    }
  };

  const signupWithEmail = async (email: string, password: string, displayName: string) => {
    setLoading(true);
    try {
      const { user: newUser } = await createUserWithEmailAndPassword(auth, email, password);
      await updateProfile(newUser, { displayName });
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async (email: string) => {
    await sendPasswordResetEmail(auth, email);
  };

  const logout = async () => {
    await auth.signOut();
    setUser(null);
  };

  return { user, loading, loginWithGoogle, loginWithEmail, signupWithEmail, resetPassword, logout };
}

import { useState, useCallback, useEffect } from "react";
import { creatorLogin, creatorRegister } from "../lib/api";

const STORAGE_KEY = "agentchains_creator_jwt";
const CREATOR_KEY = "agentchains_creator";

interface Creator {
  id: string;
  email: string;
  display_name: string;
  payout_method: string;
  status: string;
}

export function useCreatorAuth() {
  const [token, setToken] = useState<string | null>(() => {
    try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
  });
  const [creator, setCreator] = useState<Creator | null>(() => {
    try {
      const stored = localStorage.getItem(CREATOR_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAuthenticated = !!token;

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await creatorLogin({ email, password });
      localStorage.setItem(STORAGE_KEY, res.token);
      localStorage.setItem(CREATOR_KEY, JSON.stringify(res.creator));
      setToken(res.token);
      setCreator(res.creator);
      return res;
    } catch (e: any) {
      setError(e.message || "Login failed");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (data: {
    email: string;
    password: string;
    display_name: string;
    phone?: string;
    country?: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await creatorRegister(data);
      localStorage.setItem(STORAGE_KEY, res.token);
      localStorage.setItem(CREATOR_KEY, JSON.stringify(res.creator));
      setToken(res.token);
      setCreator(res.creator);
      return res;
    } catch (e: any) {
      setError(e.message || "Registration failed");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(CREATOR_KEY);
    setToken(null);
    setCreator(null);
  }, []);

  return { token, creator, isAuthenticated, loading, error, login, register, logout };
}

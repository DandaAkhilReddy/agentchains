import { useState, useCallback } from "react";

export function useAuth() {
  const [token, setToken] = useState(
    () => localStorage.getItem("agent_jwt") ?? "",
  );

  const login = useCallback((jwt: string) => {
    setToken(jwt);
    localStorage.setItem("agent_jwt", jwt);
  }, []);

  const logout = useCallback(() => {
    setToken("");
    localStorage.removeItem("agent_jwt");
  }, []);

  return { token, login, logout, isAuthenticated: !!token };
}

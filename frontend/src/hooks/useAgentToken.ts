import { useState, useCallback } from "react";

const AGENT_TOKEN_KEY = "agentchains_agent_jwt";
const AGENT_ID_KEY = "agentchains_agent_id";

interface UseAgentTokenResult {
  agentToken: string | null;
  agentId: string | null;
  hasAgent: boolean;
  setAgent: (token: string, id: string) => void;
  clearAgent: () => void;
}

/**
 * Persist agent JWT token in localStorage.
 *
 * Agent tokens are issued at onboarding time (`POST /api/v2/agents/onboard`)
 * and cannot be re-fetched from `/creators/me/agents`. The onboarding wizard
 * should call `setAgent(token, id)` after a successful onboard.
 */
export function useAgentToken(): UseAgentTokenResult {
  const [agentToken, setAgentToken] = useState<string | null>(() => {
    try { return localStorage.getItem(AGENT_TOKEN_KEY); } catch { return null; }
  });
  const [agentId, setAgentId] = useState<string | null>(() => {
    try { return localStorage.getItem(AGENT_ID_KEY); } catch { return null; }
  });

  const setAgent = useCallback((token: string, id: string) => {
    try {
      localStorage.setItem(AGENT_TOKEN_KEY, token);
      localStorage.setItem(AGENT_ID_KEY, id);
    } catch { /* localStorage unavailable */ }
    setAgentToken(token);
    setAgentId(id);
  }, []);

  const clearAgent = useCallback(() => {
    try {
      localStorage.removeItem(AGENT_TOKEN_KEY);
      localStorage.removeItem(AGENT_ID_KEY);
    } catch { /* localStorage unavailable */ }
    setAgentToken(null);
    setAgentId(null);
  }, []);

  return { agentToken, agentId, hasAgent: !!agentToken, setAgent, clearAgent };
}

import { useState, useEffect, useCallback } from "react";
import type { ChainTemplate } from "../types/chain";
import { listChainTemplates, archiveChainTemplate } from "../lib/api";

interface UseMyChains {
  chains: ChainTemplate[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  archive: (templateId: string) => Promise<void>;
}

export function useMyChains(agentToken: string, agentId: string): UseMyChains {
  const [chains, setChains] = useState<ChainTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  const refetch = useCallback(() => setRevision((r) => r + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listChainTemplates(agentToken, { author_id: agentId, limit: 100 })
      .then((res) => {
        if (!cancelled) setChains(res.templates);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load chains");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [agentToken, agentId, revision]);

  const archive = useCallback(async (templateId: string) => {
    await archiveChainTemplate(agentToken, templateId);
    refetch();
  }, [agentToken, refetch]);

  return { chains, loading, error, refetch, archive };
}

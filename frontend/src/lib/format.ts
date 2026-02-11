export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatUSDC(amount: number): string {
  if (amount < 0.01) return `$${amount.toFixed(6)}`;
  return `$${amount.toFixed(4)}`;
}

export function truncateId(id: string, len = 8): string {
  return id.length > len ? `${id.slice(0, len)}...` : id;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function scoreToPercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function formatARD(amount: number): string {
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(2)}M ARD`;
  if (amount >= 1_000) return `${(amount / 1_000).toFixed(1)}K ARD`;
  return `${amount.toFixed(2)} ARD`;
}

export function ardToUSD(amount: number, pegRate = 0.001): string {
  const usd = amount * pegRate;
  return `$${usd.toFixed(2)}`;
}

import { ShieldCheck } from "lucide-react";

export default function AuthGateBanner() {
  return (
    <div
      className="flex items-center gap-3 rounded-xl border px-4 py-3"
      style={{
        backgroundColor: "rgba(251,191,36,0.06)",
        borderColor: "rgba(251,191,36,0.15)",
      }}
    >
      <ShieldCheck className="h-4 w-4 flex-shrink-0 text-[#fbbf24]" />
      <p className="text-xs text-[#fbbf24]">
        Connect your agent JWT in the Transactions tab to enable Express Buy
      </p>
    </div>
  );
}

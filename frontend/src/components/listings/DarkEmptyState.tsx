import { PackageOpen } from "lucide-react";

export default function DarkEmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-20"
      style={{
        backgroundColor: "rgba(20,25,40,0.5)",
        borderColor: "rgba(255,255,255,0.08)",
      }}
    >
      <div
        className="mb-4 rounded-2xl p-5"
        style={{
          backgroundColor: "rgba(96,165,250,0.08)",
          boxShadow: "0 0 24px rgba(96,165,250,0.1)",
        }}
      >
        <PackageOpen className="h-10 w-10 text-[#60a5fa] animate-pulse" />
      </div>
      <p className="text-base font-medium text-[#94a3b8]">No listings found</p>
      <p className="mt-1 text-sm text-[#64748b]">
        Try adjusting your filters or search query
      </p>
    </div>
  );
}

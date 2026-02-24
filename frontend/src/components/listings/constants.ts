import { Search, Code, FileText, Globe, Cpu } from "lucide-react";

export const CATEGORY_ICONS: Record<string, typeof Search> = {
  web_search: Search,
  code_analysis: Code,
  document_summary: FileText,
  api_response: Globe,
  computation: Cpu,
};

export const CATEGORY_ACCENT: Record<string, string> = {
  web_search: "#60a5fa",
  code_analysis: "#a78bfa",
  document_summary: "#34d399",
  api_response: "#fbbf24",
  computation: "#22d3ee",
};

export const CATEGORY_GLOW: Record<string, string> = {
  web_search: "rgba(96,165,250,0.25)",
  code_analysis: "rgba(167,139,250,0.25)",
  document_summary: "rgba(52,211,153,0.25)",
  api_response: "rgba(251,191,36,0.25)",
  computation: "rgba(34,211,238,0.25)",
};

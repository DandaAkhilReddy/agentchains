import { useState } from "react";
import { FileText, Lock, Globe } from "lucide-react";
import PageHeader from "../components/PageHeader";
import CodeBlock from "../components/docs/CodeBlock";
import DocsSidebar from "../components/docs/DocsSidebar";
import { SECTIONS, SIDEBAR_GROUPS } from "./docs-sections";

// --- Method badge color helper ---

function methodColor(method: string): string {
  switch (method) {
    case "GET":
      return "bg-success/10 text-success";
    case "POST":
      return "bg-primary/10 text-primary";
    case "PUT":
      return "bg-warning/10 text-warning";
    case "DELETE":
      return "bg-danger/10 text-danger";
    case "PATCH":
      return "bg-warning/10 text-warning";
    case "WS":
      return "bg-secondary/10 text-secondary";
    case "SSE":
      return "bg-secondary/10 text-secondary";
    default:
      return "bg-surface-overlay text-text-muted";
  }
}

// --- Page Component ---

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [searchQuery, setSearchQuery] = useState("");

  const section = SECTIONS.find((s) => s.id === activeSection) ?? SECTIONS[0];

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="API Documentation"
        subtitle={`Complete reference — ${SECTIONS.length} sections covering all endpoints`}
        icon={FileText}
      />

      <div className="docs-layout">
        {/* Left Nav */}
        <DocsSidebar
          sections={SECTIONS.map((s) => ({ id: s.id, title: s.title }))}
          groups={SIDEBAR_GROUPS}
          activeId={activeSection}
          onSelect={setActiveSection}
          searchQuery={searchQuery}
          onSearch={setSearchQuery}
        />

        {/* Content */}
        <div className="px-6 overflow-y-auto">
          <div className="max-w-3xl">
            <h2 className="text-lg font-bold text-text-primary mb-2">
              {section.title}
            </h2>
            <p className="text-sm text-text-secondary leading-relaxed mb-4">
              {section.description}
            </p>

            {section.endpoints && (
              <div className="space-y-3 mb-6">
                {section.endpoints.map((ep) => (
                  <div
                    key={`${ep.method}-${ep.path}`}
                    className="rounded-lg border border-border-subtle overflow-hidden"
                  >
                    {/* Header */}
                    <div className="flex items-center gap-3 px-3 py-2 bg-surface-overlay/30">
                      <span
                        className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${methodColor(ep.method)}`}
                      >
                        {ep.method}
                      </span>
                      <code className="text-xs font-mono text-text-primary font-semibold">
                        {ep.path}
                      </code>
                      {ep.auth !== undefined && (
                        ep.auth
                          ? <Lock className="h-3 w-3 text-warning ml-1" />
                          : <Globe className="h-3 w-3 text-success ml-1" />
                      )}
                      <span className="text-xs text-text-muted ml-auto hidden sm:inline">
                        {ep.description}
                      </span>
                    </div>

                    {/* Params table */}
                    {ep.params && ep.params.length > 0 && (
                      <div className="px-3 py-2 border-t border-border-subtle">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                          Parameters
                        </p>
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-text-muted">
                              <th className="text-left font-medium py-0.5 pr-3">Name</th>
                              <th className="text-left font-medium py-0.5 pr-3">Type</th>
                              <th className="text-left font-medium py-0.5 pr-3">Req</th>
                              <th className="text-left font-medium py-0.5">Description</th>
                            </tr>
                          </thead>
                          <tbody>
                            {ep.params.map((p) => (
                              <tr key={p.name} className="text-text-secondary">
                                <td className="py-0.5 pr-3 font-mono text-text-primary">{p.name}</td>
                                <td className="py-0.5 pr-3 text-text-muted">{p.type}</td>
                                <td className="py-0.5 pr-3">
                                  {p.required ? <span className="text-danger">*</span> : "—"}
                                </td>
                                <td className="py-0.5">{p.desc}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* Response example */}
                    {ep.response && (
                      <div className="px-3 py-2 border-t border-border-subtle bg-[#0f172a]/5">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1">
                          Response
                        </p>
                        <pre className="text-[11px] font-mono text-text-secondary whitespace-pre-wrap leading-relaxed">
                          {ep.response}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {section.details && (
              <ul className="list-disc list-inside space-y-1 mb-4">
                {section.details.map((d, i) => (
                  <li key={i} className="text-xs text-text-secondary">
                    {d}
                  </li>
                ))}
              </ul>
            )}

            {/* Code block */}
            <div className="mt-4">
              <CodeBlock examples={section.code} />
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between mt-8 pt-4 border-t border-border-subtle">
              {(() => {
                const idx = SECTIONS.findIndex((s) => s.id === activeSection);
                const prev = idx > 0 ? SECTIONS[idx - 1] : null;
                const next = idx < SECTIONS.length - 1 ? SECTIONS[idx + 1] : null;
                return (
                  <>
                    {prev ? (
                      <button
                        onClick={() => setActiveSection(prev.id)}
                        className="text-xs text-text-muted hover:text-primary transition-colors"
                      >
                        &larr; {prev.title}
                      </button>
                    ) : (
                      <div />
                    )}
                    {next ? (
                      <button
                        onClick={() => setActiveSection(next.id)}
                        className="text-xs text-text-muted hover:text-primary transition-colors"
                      >
                        {next.title} &rarr;
                      </button>
                    ) : (
                      <div />
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

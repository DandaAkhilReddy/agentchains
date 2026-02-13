import { useState, useEffect, useRef, useCallback } from "react";
import { FileText, Lock, Globe, Link as LinkIcon, Check } from "lucide-react";
import PageHeader from "../components/PageHeader";
import CodeBlock from "../components/docs/CodeBlock";
import DocsSidebar from "../components/docs/DocsSidebar";
import ParamList from "../components/docs/ParamList";
import { SECTIONS, SIDEBAR_GROUPS } from "./docs-sections";
import type { DocEndpoint } from "./docs-sections";

// --- Method badge color helper ---

function methodColor(method: string): string {
  switch (method) {
    case "GET":
      return "bg-[rgba(52,211,153,0.12)] text-[#34d399] border border-[rgba(52,211,153,0.25)]";
    case "POST":
      return "bg-[rgba(96,165,250,0.12)] text-[#60a5fa] border border-[rgba(96,165,250,0.25)]";
    case "PUT":
      return "bg-[rgba(251,191,36,0.12)] text-[#fbbf24] border border-[rgba(251,191,36,0.25)]";
    case "DELETE":
      return "bg-[rgba(248,113,113,0.12)] text-[#f87171] border border-[rgba(248,113,113,0.25)]";
    case "PATCH":
      return "bg-[rgba(251,191,36,0.12)] text-[#fbbf24] border border-[rgba(251,191,36,0.25)]";
    case "WS":
      return "bg-[rgba(167,139,250,0.12)] text-[#a78bfa] border border-[rgba(167,139,250,0.25)]";
    case "SSE":
      return "bg-[rgba(34,211,238,0.12)] text-[#22d3ee] border border-[rgba(34,211,238,0.25)]";
    default:
      return "bg-[rgba(100,116,139,0.12)] text-[#64748b] border border-[rgba(100,116,139,0.25)]";
  }
}

// --- Endpoint sub-component ---

function EndpointBlock({ ep }: { ep: DocEndpoint }) {
  return (
    <div className="mb-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase ${methodColor(ep.method)}`}
        >
          {ep.method}
        </span>
        <code className="text-xs font-mono text-[#e2e8f0] font-semibold">
          {ep.path}
        </code>
        {ep.auth !== undefined &&
          (ep.auth ? (
            <Lock className="h-3 w-3 text-[#fbbf24] ml-1" />
          ) : (
            <Globe className="h-3 w-3 text-[#34d399] ml-1" />
          ))}
      </div>
      <p className="text-xs text-[#94a3b8] mb-3 leading-relaxed">{ep.description}</p>

      {ep.params && ep.params.length > 0 && <ParamList params={ep.params} />}

      {ep.response && (
        <div className="mt-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-[#64748b] mb-1.5">
            Response
          </p>
          <pre className="text-[11px] font-mono text-[#94a3b8] bg-[#0a0e1a] rounded-lg p-3 whitespace-pre-wrap leading-relaxed border border-[rgba(255,255,255,0.06)]">
            {ep.response}
          </pre>
        </div>
      )}
    </div>
  );
}

// --- Copy permalink button ---

function CopyPermalink({ sectionId }: { sectionId: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const url = `${window.location.origin}${window.location.pathname}#${sectionId}`;
    window.history.replaceState(null, "", `#${sectionId}`);
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [sectionId]);

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1"
      title="Copy permalink"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-[#34d399]" />
      ) : (
        <LinkIcon className="h-3.5 w-3.5 text-[#64748b] hover:text-[#60a5fa] transition-colors" />
      )}
    </button>
  );
}

// --- Page Component ---

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [searchQuery, setSearchQuery] = useState("");
  const sectionRefs = useRef<Map<string, HTMLElement>>(new Map());

  // --- Scrollspy via IntersectionObserver ---
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
            break;
          }
        }
      },
      {
        rootMargin: "-80px 0px -60% 0px",
        threshold: 0,
      },
    );

    sectionRefs.current.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // Sidebar click -> smooth scroll to section
  const handleSidebarSelect = useCallback((id: string) => {
    const el = sectionRefs.current.get(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      window.history.replaceState(null, "", `#${id}`);
    }
  }, []);

  // On mount: scroll to hash if present
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) {
      const el = sectionRefs.current.get(hash);
      if (el) {
        setTimeout(() => el.scrollIntoView({ block: "start" }), 100);
        setActiveSection(hash);
      }
    }
  }, []);

  // Ref callback for each section
  const setSectionRef = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) sectionRefs.current.set(id, el);
      else sectionRefs.current.delete(id);
    },
    [],
  );

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="API Documentation"
        subtitle={`Complete reference \u2014 ${SECTIONS.length} sections covering all endpoints`}
        icon={FileText}
      />

      <div className="docs-layout">
        {/* Docs Sidebar */}
        <DocsSidebar
          sections={SECTIONS.map((s) => ({ id: s.id, title: s.title }))}
          groups={SIDEBAR_GROUPS}
          activeId={activeSection}
          onSelect={handleSidebarSelect}
          searchQuery={searchQuery}
          onSearch={setSearchQuery}
        />

        {/* Scrolling content: ALL sections */}
        <div>
          {SECTIONS.map((section, sectionIndex) => (
            <section
              key={section.id}
              id={section.id}
              ref={setSectionRef(section.id)}
              className="docs-section"
            >
              {/* LEFT COLUMN: Text + Endpoints + Params */}
              <div className="docs-section-text">
                <div className="group flex items-center gap-2 mb-4">
                  <h2 className="text-lg font-bold text-[#e2e8f0]">
                    {section.title}
                  </h2>
                  <CopyPermalink sectionId={section.id} />
                </div>

                <p className="text-sm text-[#94a3b8] leading-relaxed mb-6">
                  {section.description}
                </p>

                {section.endpoints?.map((ep) => (
                  <EndpointBlock
                    key={`${ep.method}-${ep.path}`}
                    ep={ep}
                  />
                ))}

                {section.details && (
                  <div className="mt-4 space-y-2 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
                    {section.details.map((d, i) => (
                      <p
                        key={i}
                        className="text-xs text-[#94a3b8] leading-relaxed"
                      >
                        <span className="text-[#64748b] mr-1.5">&mdash;</span>
                        {d}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              {/* RIGHT COLUMN: Sticky code block */}
              <div className="docs-section-code">
                <CodeBlock examples={section.code} />
              </div>

              {/* Section divider (except last) */}
              {sectionIndex < SECTIONS.length - 1 && (
                <div className="col-span-full h-px bg-gradient-to-r from-transparent via-[rgba(255,255,255,0.06)] to-transparent" />
              )}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

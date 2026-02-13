import { useState, useEffect, useRef, useCallback } from "react";
import { FileText, Lock, Globe, Link as LinkIcon } from "lucide-react";
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

// --- Endpoint sub-component ---

function EndpointBlock({ ep }: { ep: DocEndpoint }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${methodColor(ep.method)}`}
        >
          {ep.method}
        </span>
        <code className="text-xs font-mono text-text-primary font-semibold">
          {ep.path}
        </code>
        {ep.auth !== undefined &&
          (ep.auth ? (
            <Lock className="h-3 w-3 text-warning ml-1" />
          ) : (
            <Globe className="h-3 w-3 text-success ml-1" />
          ))}
      </div>
      <p className="text-xs text-text-secondary mb-3">{ep.description}</p>

      {ep.params && ep.params.length > 0 && <ParamList params={ep.params} />}

      {ep.response && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1">
            Response
          </p>
          <pre className="text-[11px] font-mono text-text-secondary bg-surface-overlay/40 rounded-lg p-3 whitespace-pre-wrap leading-relaxed border border-border-subtle">
            {ep.response}
          </pre>
        </div>
      )}
    </div>
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
        subtitle={`Complete reference — ${SECTIONS.length} sections covering all endpoints`}
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
          {SECTIONS.map((section) => (
            <section
              key={section.id}
              id={section.id}
              ref={setSectionRef(section.id)}
              className="docs-section"
            >
              {/* LEFT COLUMN: Text + Endpoints + Params */}
              <div className="docs-section-text">
                <div className="group flex items-center gap-2 mb-3">
                  <h2 className="text-lg font-bold text-text-primary">
                    {section.title}
                  </h2>
                  <a
                    href={`#${section.id}`}
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.preventDefault();
                      window.history.replaceState(
                        null,
                        "",
                        `#${section.id}`,
                      );
                      navigator.clipboard.writeText(
                        `${window.location.origin}${window.location.pathname}#${section.id}`,
                      );
                    }}
                  >
                    <LinkIcon className="h-4 w-4 text-text-muted hover:text-primary" />
                  </a>
                </div>

                <p className="text-sm text-text-secondary leading-relaxed mb-6">
                  {section.description}
                </p>

                {section.endpoints?.map((ep) => (
                  <EndpointBlock
                    key={`${ep.method}-${ep.path}`}
                    ep={ep}
                  />
                ))}

                {section.details && (
                  <div className="mt-4 space-y-1.5">
                    {section.details.map((d, i) => (
                      <p
                        key={i}
                        className="text-xs text-text-secondary leading-relaxed"
                      >
                        <span className="text-text-muted mr-1">—</span>{" "}
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
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

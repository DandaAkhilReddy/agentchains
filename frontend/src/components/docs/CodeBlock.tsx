import { useState, useMemo, useCallback } from "react";
import { Copy, Check } from "lucide-react";

export interface CodeExample {
  language: string;
  code: string;
}

interface Props {
  examples: CodeExample[];
  title?: string;
  className?: string;
}

const KEYWORDS = new Set([
  "import",
  "from",
  "def",
  "const",
  "let",
  "async",
  "await",
  "return",
  "if",
  "else",
  "for",
  "class",
  "function",
  "export",
  "default",
  "new",
  "try",
  "catch",
]);

const KEYWORD_PATTERN = new RegExp(
  `\\b(${[...KEYWORDS].join("|")})\\b`,
  "g",
);

/**
 * Apply basic syntax highlighting via regex replacements.
 * Order matters: strings first (to avoid highlighting keywords inside strings),
 * then comments, keywords, and numbers.
 */
function highlight(code: string): string {
  // Unique placeholder tokens that won't appear in user code
  const PH = "\x00";
  let counter = 0;
  const replacements: string[] = [];

  function placeholder(html: string): string {
    const idx = counter++;
    replacements.push(html);
    return `${PH}${idx}${PH}`;
  }

  // Escape HTML entities first
  let result = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 1. Strings: single-quoted, double-quoted, backtick (no multiline)
  result = result.replace(
    /(["'`])(?:(?!\1|\\).|\\.)*?\1/g,
    (m) => placeholder(`<span class="string">${m}</span>`),
  );

  // 2. Comments: # or //
  result = result.replace(
    /(#.*|\/\/.*)/g,
    (m) => placeholder(`<span class="comment">${m}</span>`),
  );

  // 3. Keywords
  result = result.replace(
    KEYWORD_PATTERN,
    (m) => placeholder(`<span class="keyword">${m}</span>`),
  );

  // 4. Numbers
  result = result.replace(
    /\b(\d+(?:\.\d+)?)\b/g,
    (m) => placeholder(`<span class="number">${m}</span>`),
  );

  // Rehydrate placeholders
  result = result.replace(
    new RegExp(`${PH}(\\d+)${PH}`, "g"),
    (_, idx) => replacements[Number(idx)] ?? "",
  );

  return result;
}

/** Code block with language tabs and copy-to-clipboard. */
export default function CodeBlock({
  examples,
  title,
  className = "",
}: Props) {
  const [activeLanguage, setActiveLanguage] = useState(
    examples[0]?.language ?? "",
  );
  const [copied, setCopied] = useState(false);

  const activeExample = useMemo(
    () => examples.find((e) => e.language === activeLanguage) ?? examples[0],
    [examples, activeLanguage],
  );

  const highlighted = useMemo(
    () => (activeExample ? highlight(activeExample.code) : ""),
    [activeExample],
  );

  const handleCopy = useCallback(async () => {
    if (!activeExample) return;
    await navigator.clipboard.writeText(activeExample.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [activeExample]);

  if (examples.length === 0) return null;

  return (
    <div className={`code-block overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-0">
        {/* Title + language tabs */}
        <div className="flex items-center gap-2">
          {title && (
            <span className="text-xs font-semibold text-[#94a3b8] pr-2">
              {title}
            </span>
          )}
          <div className="flex">
            {examples.map((ex) => {
              const isActive = ex.language === activeLanguage;
              return (
                <button
                  key={ex.language}
                  type="button"
                  onClick={() => setActiveLanguage(ex.language)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-t transition-colors ${
                    isActive
                      ? "bg-[#1e293b] text-white"
                      : "text-[#64748b] hover:text-[#94a3b8]"
                  }`}
                >
                  {ex.language}
                </button>
              );
            })}
          </div>
        </div>

        {/* Copy button */}
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded px-2 py-1 text-[#64748b] hover:text-[#94a3b8] transition-colors"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <Check size={14} className="text-[#16a34a]" />
              <span className="text-[11px]">Copied</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span className="text-[11px]">Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code area */}
      <pre className="p-4 overflow-x-auto text-sm leading-relaxed m-0">
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
    </div>
  );
}

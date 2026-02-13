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
  "true",
  "false",
  "True",
  "False",
  "None",
  "null",
  "undefined",
  "with",
  "as",
  "json",
  "print",
  "console",
]);

const KEYWORD_PATTERN = new RegExp(
  `\\b(${[...KEYWORDS].join("|")})\\b`,
  "g",
);

/**
 * Apply syntax highlighting via regex with safe placeholders.
 *
 * Key fix: placeholder tokens use the format \x00R{idx}\x00 (with an "R" prefix)
 * so the number regex \b\d+\b cannot match the index digits inside placeholders.
 * Strings are captured BEFORE HTML-escaping to correctly match quoted content.
 */
function highlight(code: string): string {
  const PH = "\x00";
  let counter = 0;
  const replacements: string[] = [];

  function ph(html: string): string {
    const idx = counter++;
    replacements.push(html);
    return `${PH}R${idx}${PH}`;
  }

  // 1. Capture strings BEFORE HTML-escaping (so " and ' are real quotes)
  let result = code.replace(
    /(["'`])(?:(?!\1|\\).|\\.)*?\1/g,
    (m) => {
      // HTML-escape the string content
      const safe = m
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      return ph(`<span class="hl-string">${safe}</span>`);
    },
  );

  // 2. Now HTML-escape the rest (non-string parts)
  result = result.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // 3. Comments: # or //
  result = result.replace(
    /(#.*|\/\/.*)/g,
    (m) => ph(`<span class="hl-comment">${m}</span>`),
  );

  // 4. Keywords
  result = result.replace(
    KEYWORD_PATTERN,
    (m) => ph(`<span class="hl-keyword">${m}</span>`),
  );

  // 5. Method/function calls: .methodName(
  result = result.replace(
    /\.([a-zA-Z_]\w*)\s*\(/g,
    (_full, name) => `.${ph(`<span class="hl-method">${name}</span>`)}(`,
  );

  // 6. Numbers (safe now — placeholder indices have "R" prefix, won't match \b\d+\b)
  result = result.replace(
    /\b(\d+(?:\.\d+)?)\b/g,
    (m) => ph(`<span class="hl-number">${m}</span>`),
  );

  // Rehydrate placeholders — match \x00R{digits}\x00
  result = result.replace(
    new RegExp(`${PH}R(\\d+)${PH}`, "g"),
    (_, idx) => replacements[Number(idx)] ?? "",
  );

  return result;
}

/** Code block with language tabs, copy-to-clipboard, and frosted glass design. */
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
    <div className={`code-block ${className}`}>
      {/* Header — macOS-style chrome */}
      <div className="code-block-header">
        {/* Traffic light dots */}
        <div className="flex items-center gap-1.5 mr-3">
          <span className="h-[10px] w-[10px] rounded-full bg-[#ff5f57]/80" />
          <span className="h-[10px] w-[10px] rounded-full bg-[#febc2e]/80" />
          <span className="h-[10px] w-[10px] rounded-full bg-[#28c840]/80" />
        </div>

        {/* Title + language tabs */}
        <div className="flex items-center gap-1 flex-1 min-w-0">
          {title && (
            <span className="text-[11px] font-medium text-[#64748b] pr-2 truncate">
              {title}
            </span>
          )}
          <div className="flex gap-0.5">
            {examples.map((ex) => {
              const isActive = ex.language === activeLanguage;
              return (
                <button
                  key={ex.language}
                  type="button"
                  onClick={() => setActiveLanguage(ex.language)}
                  className={`code-block-tab ${isActive ? "active" : ""}`}
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
          className="code-block-copy"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <Check size={13} className="text-[#4ade80]" />
              <span>Copied</span>
            </>
          ) : (
            <>
              <Copy size={13} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code area */}
      <pre className="code-block-pre">
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
    </div>
  );
}

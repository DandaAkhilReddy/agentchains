import { useState, useCallback, useMemo } from "react";
import { Copy, Check, Code2 } from "lucide-react";

/**
 * A2UI Code Widget.
 *
 * Renders a code block with optional line numbers, a language badge,
 * syntax highlight lines, and a one-click copy button.
 * Uses pre/code tags with a monospace font for consistent display.
 */

interface A2UICodeWidgetProps {
  code: string;
  language?: string;
  showLineNumbers?: boolean;
  highlightLines?: number[];
}

export default function A2UICodeWidget({
  code,
  language,
  showLineNumbers = true,
  highlightLines = [],
}: A2UICodeWidgetProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = code;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [code]);

  const lines = useMemo(() => code.split("\n"), [code]);
  const highlightSet = useMemo(() => new Set(highlightLines), [highlightLines]);

  // Determine gutter width based on line count
  const gutterWidth = useMemo(() => {
    const digits = String(lines.length).length;
    return Math.max(digits * 0.6 + 0.8, 2.2);
  }, [lines.length]);

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#0d1220] overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] bg-[#141928] px-4 py-2.5">
        <div className="flex items-center gap-2">
          {/* Traffic light dots */}
          <div className="flex items-center gap-1.5 mr-3">
            <div className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
            <div className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
            <div className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          </div>

          {/* Language badge */}
          {language && (
            <span className="inline-flex items-center gap-1 rounded-md bg-[rgba(96,165,250,0.1)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#60a5fa]">
              <Code2 className="h-2.5 w-2.5" />
              {language}
            </span>
          )}
        </div>

        {/* Copy button */}
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-[#64748b] transition-all duration-200 hover:bg-[rgba(255,255,255,0.04)] hover:text-[#e2e8f0] active:scale-95"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-[#34d399]" />
              <span className="text-[#34d399]">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code content */}
      <div className="overflow-x-auto">
        <pre className="m-0 p-0" style={{ fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace" }}>
          <code className="block text-xs leading-6 text-[#e2e8f0]">
            {lines.map((line, index) => {
              const lineNum = index + 1;
              const isHighlighted = highlightSet.has(lineNum);

              return (
                <div
                  key={index}
                  className="flex transition-colors duration-150"
                  style={{
                    backgroundColor: isHighlighted
                      ? "rgba(96,165,250,0.08)"
                      : "transparent",
                    borderLeft: isHighlighted
                      ? "2px solid #60a5fa"
                      : "2px solid transparent",
                  }}
                >
                  {/* Line number gutter */}
                  {showLineNumbers && (
                    <span
                      className="flex-shrink-0 select-none text-right text-[#475569] pr-4 pl-4"
                      style={{
                        width: `${gutterWidth}rem`,
                        minWidth: `${gutterWidth}rem`,
                      }}
                    >
                      {lineNum}
                    </span>
                  )}

                  {/* Code line content */}
                  <span
                    className="flex-1 pr-6"
                    style={{
                      paddingLeft: showLineNumbers ? "0" : "1.5rem",
                      whiteSpace: "pre",
                    }}
                  >
                    {line || "\n"}
                  </span>
                </div>
              );
            })}
          </code>
        </pre>
      </div>

      {/* Footer: line count */}
      <div className="flex items-center justify-between border-t border-[rgba(255,255,255,0.06)] bg-[#141928] px-4 py-1.5">
        <span className="text-[10px] text-[#475569]">
          {lines.length} line{lines.length !== 1 ? "s" : ""}
        </span>
        {highlightLines.length > 0 && (
          <span className="text-[10px] text-[#60a5fa]">
            {highlightLines.length} highlighted
          </span>
        )}
      </div>
    </div>
  );
}

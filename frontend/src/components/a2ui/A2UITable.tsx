import { useState, useMemo } from "react";

/**
 * A2UI Table widget.
 *
 * Renders a data table with headers and rows from the agent-provided data.
 * Supports optional title, caption, and sortable columns.
 */
interface A2UITableProps {
  data: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export default function A2UITable({ data, metadata }: A2UITableProps) {
  const {
    title,
    caption,
    headers,
    rows,
    sortable,
  } = data as {
    title?: string;
    caption?: string;
    headers?: string[];
    rows?: Array<Array<string | number>>;
    sortable?: boolean;
  };

  const tableHeaders = headers ?? [];
  const tableRows = rows ?? [];
  const isSortable = sortable !== false && tableHeaders.length > 0;

  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const sortedRows = useMemo(() => {
    if (sortCol === null || !isSortable) return tableRows;
    return [...tableRows].sort((a, b) => {
      const valA = a[sortCol] ?? "";
      const valB = b[sortCol] ?? "";
      if (typeof valA === "number" && typeof valB === "number") {
        return sortAsc ? valA - valB : valB - valA;
      }
      const strA = String(valA).toLowerCase();
      const strB = String(valB).toLowerCase();
      if (strA < strB) return sortAsc ? -1 : 1;
      if (strA > strB) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [tableRows, sortCol, sortAsc, isSortable]);

  const handleSort = (colIdx: number) => {
    if (!isSortable) return;
    if (sortCol === colIdx) {
      setSortAsc((prev) => !prev);
    } else {
      setSortCol(colIdx);
      setSortAsc(true);
    }
  };

  if (tableHeaders.length === 0 && tableRows.length === 0) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
        <p className="text-sm text-[#64748b]">No table data provided.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
      {/* Optional title */}
      {title && (
        <div className="border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
          <h3 className="text-sm font-semibold text-[#e2e8f0]">{title}</h3>
          {caption && (
            <p className="mt-0.5 text-xs text-[#64748b]">{caption}</p>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {tableHeaders.length > 0 && (
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
                {tableHeaders.map((header, i) => (
                  <th
                    key={i}
                    onClick={() => handleSort(i)}
                    className={`px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#64748b] ${
                      isSortable
                        ? "cursor-pointer select-none transition-colors hover:text-[#94a3b8]"
                        : ""
                    }`}
                  >
                    <span className="inline-flex items-center gap-1">
                      {header}
                      {isSortable && sortCol === i && (
                        <span className="text-[#60a5fa]">
                          {sortAsc ? "\u2191" : "\u2193"}
                        </span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {sortedRows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className={`border-b border-[rgba(255,255,255,0.04)] transition-colors hover:bg-[rgba(96,165,250,0.04)] ${
                  rowIdx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                }`}
              >
                {row.map((cell, cellIdx) => (
                  <td
                    key={cellIdx}
                    className="px-4 py-3 text-[#e2e8f0]"
                  >
                    {String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Metadata footer */}
      {metadata && Object.keys(metadata).length > 0 && (
        <div className="border-t border-[rgba(255,255,255,0.06)] px-6 py-3">
          <div className="flex flex-wrap gap-4 text-xs text-[#64748b]">
            {Object.entries(metadata).map(([key, val]) => (
              <span key={key}>
                {key}: <span className="text-[#94a3b8]">{String(val)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

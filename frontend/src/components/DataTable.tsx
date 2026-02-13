import type { ReactNode } from "react";
import Spinner from "./Spinner";
import EmptyState from "./EmptyState";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
  align?: "left" | "center" | "right";
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  isLoading: boolean;
  keyFn: (row: T) => string;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  containerClassName?: string;
}

const ALIGN_MAP = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

export default function DataTable<T>({
  columns,
  data,
  isLoading,
  keyFn,
  emptyMessage = "No data found",
  onRowClick,
  containerClassName,
}: Props<T>) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 bg-[#141928] rounded-2xl border border-[rgba(255,255,255,0.06)]">
        <Spinner />
      </div>
    );
  }

  if (data.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className={`bg-[#141928] rounded-2xl border border-[rgba(255,255,255,0.06)] overflow-hidden ${containerClassName ?? ""}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`sticky top-0 px-4 py-3 text-xs font-medium uppercase tracking-wider text-[#64748b] ${ALIGN_MAP[col.align ?? "left"]} ${col.className ?? ""}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr
                key={keyFn(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-b border-[rgba(255,255,255,0.04)] transition-colors duration-200 ${
                  idx % 2 === 1 ? "bg-[rgba(255,255,255,0.01)]" : ""
                } ${
                  onRowClick
                    ? "cursor-pointer hover:bg-[rgba(96,165,250,0.04)]"
                    : "hover:bg-[rgba(96,165,250,0.04)]"
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 text-[#e2e8f0] ${ALIGN_MAP[col.align ?? "left"]} ${col.className ?? ""}`}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

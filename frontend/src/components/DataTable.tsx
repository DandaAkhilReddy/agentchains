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
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  if (data.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className={`glass-card overflow-hidden border border-border-subtle ${containerClassName ?? ""}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-surface-overlay/30">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`sticky top-0 px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-text-muted ${ALIGN_MAP[col.align ?? "left"]} ${col.className ?? ""}`}
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
                className={`border-b border-border-subtle/30 transition-colors duration-200 ${
                  idx % 2 === 1 ? "bg-surface-raised/30" : ""
                } ${
                  onRowClick
                    ? "cursor-pointer hover:bg-primary-glow hover:border-l-2 hover:border-l-primary"
                    : "hover:bg-[rgba(59,130,246,0.04)]"
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 ${ALIGN_MAP[col.align ?? "left"]} ${col.className ?? ""}`}
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

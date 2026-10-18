import { cn } from "cn";
import { ArrowDownIcon, ArrowUpIcon, ChevronsUpDownIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export type Column<Row> = {
  header: string;
  cell: (row: Row) => ReactNode;
  /** "end" for numbers, so digits line up. */
  align?: "start" | "end";
  /** The column used as the title of each card on phones. Exactly one column should set this. */
  primary?: boolean;
  /** Set to make the column sortable: clicking its header sorts by this key. */
  sortKey?: string;
};

export type TableSort = { key: string; direction: "asc" | "desc" };

const loadingRowCount = 4;

// A table on tablets and computers. On phones, each row becomes a small card,
// so nobody has to scroll sideways.
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  loading = false,
  sort,
  onSort,
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  loading?: boolean;
  sort?: TableSort;
  onSort?: (sort: TableSort) => void;
}) {
  const primary = columns.find((column) => column.primary) ?? columns[0];
  const details = columns.filter((column) => column !== primary);

  return (
    <div aria-busy={loading || undefined}>
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((column) => {
                const sorted = sort && column.sortKey === sort.key ? sort.direction : undefined;
                return (
                  <TableHead
                    key={column.header}
                    className={alignClass(column)}
                    aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
                  >
                    {column.sortKey && onSort ? (
                      <SortButton
                        label={column.header}
                        direction={sorted}
                        alignEnd={column.align === "end"}
                        onClick={() =>
                          onSort({ key: column.sortKey!, direction: sorted === "asc" ? "desc" : "asc" })
                        }
                      />
                    ) : (
                      column.header
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? range(loadingRowCount).map((index) => (
                  <TableRow key={index}>
                    {columns.map((column) => (
                      <TableCell key={column.header}>
                        <Skeleton className={cn("h-4 w-20", column.align === "end" && "ms-auto w-12")} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : rows.map((row) => (
                  <TableRow key={rowKey(row)}>
                    {columns.map((column) => (
                      <TableCell key={column.header} className={alignClass(column)}>
                        {column.cell(row)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>

      <ul className="divide-y border-t md:hidden">
        {loading
          ? range(loadingRowCount).map((index) => (
              <li key={index} className="grid gap-3 px-6 py-4">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </li>
            ))
          : rows.map((row) => (
              <li key={rowKey(row)} className="grid gap-3 px-6 py-4">
                <div className="text-title-medium">{primary.cell(row)}</div>
                <dl className="grid gap-2">
                  {details.map((column) => (
                    <div key={column.header} className="flex items-center justify-between gap-4">
                      <dt className="text-body-small text-on-surface-variant">{column.header}</dt>
                      <dd className={cn("text-end", column.align === "end" && "tabular-nums")}>{column.cell(row)}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
      </ul>
    </div>
  );
}

// Number columns line up at the end, with same-width digits.
// Clicking a header sorts by it; clicking again flips the order.
function SortButton({
  label,
  direction,
  alignEnd,
  onClick,
}: {
  label: string;
  direction?: "asc" | "desc";
  alignEnd: boolean;
  onClick: () => void;
}) {
  const Icon = direction === "asc" ? ArrowUpIcon : direction === "desc" ? ArrowDownIcon : ChevronsUpDownIcon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "-mx-1 inline-flex items-center gap-1 rounded-xs px-1 py-0.5 hover:text-on-surface",
        direction && "text-on-surface",
        alignEnd && "flex-row-reverse",
      )}
    >
      {label}
      <Icon aria-hidden="true" className={cn("size-3.5", !direction && "opacity-50")} />
    </button>
  );
}

function alignClass(column: { align?: "start" | "end" }) {
  return column.align === "end" ? "text-end tabular-nums" : "text-start";
}

function range(count: number) {
  return Array.from({ length: count }, (_, index) => index);
}

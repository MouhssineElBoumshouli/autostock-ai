import { cn } from "cn";
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
};

const loadingRowCount = 4;

// A table on tablets and computers. On phones, each row becomes a small card,
// so nobody has to scroll sideways.
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  loading = false,
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  loading?: boolean;
}) {
  const primary = columns.find((column) => column.primary) ?? columns[0];
  const details = columns.filter((column) => column !== primary);

  return (
    <div aria-busy={loading || undefined}>
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((column) => (
                <TableHead key={column.header} className={alignClass(column)}>
                  {column.header}
                </TableHead>
              ))}
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
                <div className="font-medium">{primary.cell(row)}</div>
                <dl className="grid gap-2">
                  {details.map((column) => (
                    <div key={column.header} className="flex items-center justify-between gap-4">
                      <dt className="text-xs text-muted-foreground">{column.header}</dt>
                      <dd className="text-end">{column.cell(row)}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
      </ul>
    </div>
  );
}

function alignClass(column: { align?: "start" | "end" }) {
  return column.align === "end" ? "text-end" : "text-start";
}

function range(count: number) {
  return Array.from({ length: count }, (_, index) => index);
}

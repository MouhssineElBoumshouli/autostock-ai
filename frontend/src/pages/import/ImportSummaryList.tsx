import type { ImportSummary } from "@/api/imports";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// "142 new parts · 12 parts updated · 3 rows with problems", plus new branches and suppliers.
export function ImportSummaryList({ summary }: { summary: ImportSummary }) {
  const lines = Object.entries(summary.counts)
    .filter(([key, value]) => value > 0 && t.importFile.counts[key])
    .map(([key, value]) => t.importFile.counts[key](formatNumber(value)));
  if (summary.new_branches.length > 0) lines.push(t.importFile.newBranches(summary.new_branches.join(", ")));
  if (summary.new_suppliers.length > 0) {
    lines.push(t.importFile.newSuppliers(formatNumber(summary.new_suppliers.length), summary.new_suppliers.join(", ")));
  }

  return (
    <ul className="grid gap-2">
      {lines.map((line) => (
        <li key={line} className="flex gap-2 text-sm">
          <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-foreground" />
          {line}
        </li>
      ))}
    </ul>
  );
}

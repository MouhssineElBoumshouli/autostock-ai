import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// "26–50 of 80" with Previous and Next, under a list.
export function Pagination({
  page,
  pageSize,
  total,
  shown,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  shown: number;
  onPage: (page: number) => void;
}) {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = from + shown - 1;
  const lastPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <nav aria-label={t.common.pages} className="flex items-center justify-between gap-4 border-t px-6 py-3">
      <p className="text-body-medium text-on-surface-variant tabular-nums">
        {t.common.showing(formatNumber(from), formatNumber(Math.max(from, to)), formatNumber(total))}
      </p>
      <div className="flex gap-2">
        <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          {t.common.previous}
        </Button>
        <Button size="sm" disabled={page >= lastPage} onClick={() => onPage(page + 1)}>
          {t.common.next}
        </Button>
      </div>
    </nav>
  );
}

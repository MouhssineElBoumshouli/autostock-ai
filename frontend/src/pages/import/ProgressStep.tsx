import type { ImportJob } from "@/api/imports";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// While a big file is checked or saved in the background: how far it got. The numbers come from the
// server, so a page reload finds them again and leaving the page changes nothing.
export function ProgressStep({ job }: { job: ImportJob }) {
  const words = job.status === "saving" ? t.importFile.progress.saving : t.importFile.progress.checking;
  const percent = job.rows_total > 0 ? Math.min(100, Math.round((job.rows_done / job.rows_total) * 100)) : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{job.preview.file_name}</CardTitle>
        <CardDescription>{words}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={job.finishing ? 100 : percent}
          aria-label={words}
          className="h-2 w-full overflow-hidden rounded-full bg-surface-container-high"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-500"
            style={{ width: `${job.finishing ? 100 : percent}%` }}
          />
        </div>
        <p className="text-title-medium tabular-nums" role="status">
          {job.finishing
            ? t.importFile.progress.finishing
            : t.importFile.progress.rows(formatNumber(job.rows_done), formatNumber(job.rows_total))}
        </p>
        <p className="text-body-medium text-on-surface-variant">{t.importFile.progress.canLeave}</p>
      </CardContent>
    </Card>
  );
}

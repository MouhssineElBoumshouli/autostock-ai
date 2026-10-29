import { useBackups } from "@/api/backups";
import { ErrorState } from "@/components/ErrorState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatDayAndTime, formatNumber } from "@/lib/format";

// Owners only: when the last good backup was made, and the reminder to copy the folder elsewhere.
// Hidden while developing (no backups then).
export function BackupsCard() {
  const backups = useBackups();
  const words = t.settings.backups;
  if (backups.data && !backups.data.on) return null;

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{words.title}</CardTitle>
      </CardHeader>
      {backups.isError ? (
        <ErrorState onRetry={() => backups.refetch()} retrying={backups.isFetching} />
      ) : backups.isPending ? (
        <CardContent aria-busy="true">
          <Skeleton className="h-10 w-full" />
        </CardContent>
      ) : (
        <CardContent className="grid gap-3">
          <p className="text-body-large">
            {backups.data.last_good_at
              ? words.lastBackup(formatDayAndTime(backups.data.last_good_at), formatNumber(backups.data.kept))
              : words.none}
          </p>
          {backups.data.problem && <p className="text-body-medium text-error">{words.problems[backups.data.problem]}</p>}
          <p className="text-body-medium text-on-surface-variant">{words.copyReminder}</p>
        </CardContent>
      )}
    </Card>
  );
}

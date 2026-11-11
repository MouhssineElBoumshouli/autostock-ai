import { TriangleAlertIcon } from "lucide-react";
import { Link } from "react-router";

import type { AlertSummary, Today } from "@/api/today";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatDayAndTime } from "@/lib/format";

import { AlertRow } from "./AlertRow";

// Stock that doesn't match sales: the alerts an owner or manager should act on first. Owners also
// see here when the backups stopped.
export function NeedsActionCard({
  alerts,
  total,
  canReview,
  backupOverdue,
}: {
  alerts: AlertSummary[];
  total: number;
  canReview: boolean;
  backupOverdue: Today["backup_overdue"];
}) {
  return (
    <Card className="gap-2 pb-2">
      <CardHeader>
        <CardTitle>{t.home.needsAction.title}</CardTitle>
        {total > 0 && (
          <CardAction>
            <Button variant="text" size="sm" asChild className="-me-3">
              <Link to="/alerts?group=needs_action">{t.home.seeAllAlerts}</Link>
            </Button>
          </CardAction>
        )}
      </CardHeader>
      {alerts.length === 0 && !backupOverdue ? (
        <EmptyState icon={TriangleAlertIcon} title={t.home.needsAction.empty} />
      ) : (
        <ul className="divide-y">
          {backupOverdue && <BackupOverdueRow lastGoodAt={backupOverdue.last_good_at} />}
          {alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} canReview={canReview} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function BackupOverdueRow({ lastGoodAt }: { lastGoodAt: string | null }) {
  const words = t.home.needsAction;
  return (
    <li className="grid gap-2 px-6 py-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
      <p className="text-body-large text-error">{lastGoodAt ? words.backupOverdue(formatDayAndTime(lastGoodAt)) : words.backupNone}</p>
      <Button variant="tonal" size="sm" asChild className="justify-self-start">
        <Link to="/settings">{words.backupOpenSettings}</Link>
      </Button>
    </li>
  );
}

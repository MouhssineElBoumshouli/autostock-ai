import { TriangleAlertIcon } from "lucide-react";
import { Link } from "react-router";

import type { AlertSummary } from "@/api/today";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";

import { AlertRow } from "./AlertRow";

// Stock that doesn't match sales: the alerts an owner or manager should act on first.
export function NeedsActionCard({
  alerts,
  total,
  canReview,
}: {
  alerts: AlertSummary[];
  total: number;
  canReview: boolean;
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
      {alerts.length === 0 ? (
        <EmptyState icon={TriangleAlertIcon} title={t.home.needsAction.empty} />
      ) : (
        <ul className="divide-y">
          {alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} canReview={canReview} />
          ))}
        </ul>
      )}
    </Card>
  );
}

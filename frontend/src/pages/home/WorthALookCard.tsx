import { TrendingUpIcon } from "lucide-react";
import { Link } from "react-router";

import type { AlertSummary } from "@/api/today";
import { EmptyState } from "@/components/EmptyState";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { alertSentence } from "@/lib/alertSentence";

// Sales spikes and drops: good to know, nothing to fix. Smaller and below the action items.
export function WorthALookCard({ alerts, total }: { alerts: AlertSummary[]; total: number }) {
  const currency = useSignedIn().organization.currency;
  return (
    <Card className="gap-2 pb-2">
      <CardHeader>
        <CardTitle className="text-title-small">{t.home.worthALook.title}</CardTitle>
        {total > 0 && (
          <CardAction>
            <Button variant="text" size="sm" asChild className="-me-3">
              <Link to="/alerts?group=worth_a_look">{t.home.seeAllAlerts}</Link>
            </Button>
          </CardAction>
        )}
      </CardHeader>
      {alerts.length === 0 ? (
        <EmptyState icon={TrendingUpIcon} title={t.home.worthALook.empty} />
      ) : (
        <ul className="divide-y">
          {alerts.map((alert) => (
            <li key={alert.id} className="grid gap-0.5 px-6 py-3">
              <p className="text-body-medium">{alertSentence(alert, currency)}</p>
              <p className="text-body-small text-on-surface-variant">
                {alert.part_name} · {alert.branch_name}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

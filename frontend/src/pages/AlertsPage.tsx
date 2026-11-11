import { TriangleAlertIcon } from "lucide-react";
import { useSearchParams } from "react-router";

import { type AlertGroup, type AlertStatus, useAlerts } from "@/api/alerts";
import { useSignedIn } from "@/components/SignedIn";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ALL, FilterChip } from "@/components/FilterChip";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

import { AlertRow } from "./home/AlertRow";

const groups: AlertGroup[] = ["needs_action", "worth_a_look"];
const statuses: AlertStatus[] = ["open", "looked_at", "not_a_problem"];

// Every alert, filterable by group and status, newest first. Owners and managers can still mark
// one from here; staff can only look.
export function AlertsPage() {
  const canReview = useSignedIn().user.role !== "staff";
  const [params, setParams] = useSearchParams();
  const filters = {
    group: (params.get("group") as AlertGroup | null) ?? undefined,
    status: (params.get("status") as AlertStatus | null) ?? undefined,
  };
  const alerts = useAlerts(filters);
  const filtered = Boolean(filters.group || filters.status);

  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value && value !== ALL) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  }

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.alerts} subtitle={t.alertsPage.subtitle} />

      <div className="flex flex-wrap gap-2">
        <FilterChip
          label={t.alertsPage.group}
          value={filters.group}
          allLabel={t.alertsPage.allGroups}
          options={groups.map((group) => ({ value: group, label: t.alertsPage.groups[group] }))}
          onChange={(group) => update({ group })}
        />
        <FilterChip
          label={t.alertsPage.status}
          value={filters.status}
          allLabel={t.alertsPage.allStatuses}
          options={statuses.map((status) => ({ value: status, label: t.alertsPage.statuses[status] }))}
          onChange={(status) => update({ status })}
        />
      </div>

      <Card className="py-0">
        {alerts.isError ? (
          <ErrorState onRetry={() => alerts.refetch()} retrying={alerts.isFetching} />
        ) : alerts.isPending ? (
          <div className="grid gap-3 px-6 py-4" aria-busy="true">
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-14 w-full" />
            ))}
          </div>
        ) : alerts.data && alerts.data.length === 0 ? (
          <EmptyState
            icon={TriangleAlertIcon}
            title={filtered ? t.alertsPage.nothingMatches : t.alertsPage.nothingYet}
          />
        ) : (
          <ul className="divide-y">
            {alerts.data?.map((alert) => (
              <AlertRow
                key={alert.id}
                alert={alert}
                canReview={canReview}
                status={alert.status}
                reviewedByName={alert.reviewed_by_name}
                reviewedAt={alert.reviewed_at}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

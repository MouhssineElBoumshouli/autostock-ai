import { HistoryIcon } from "lucide-react";
import { useSearchParams } from "react-router";

import { type ActivityKind, activityKinds, useActivity, useActivityPeople } from "@/api/activity";
import { ActivityList } from "@/components/ActivityList";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { FormField } from "@/components/FormField";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { t } from "@/i18n";

const ALL = "all";

// The full history, 25 per page. Filters live in the address, so the back button and links keep them.
export function ActivityPage() {
  const [params, setParams] = useSearchParams();
  const filters = {
    page: Math.max(1, Number(params.get("page")) || 1),
    person: params.get("person") ?? undefined,
    kind: (params.get("kind") as ActivityKind | null) ?? undefined,
  };
  const activity = useActivity(filters);
  const people = useActivityPeople();
  const filtered = Boolean(filters.person || filters.kind);

  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value && value !== ALL) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  }

  const data = activity.data;
  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const from = data ? (data.page - 1) * data.page_size + 1 : 0;
  const to = data ? from + data.items.length - 1 : 0;

  return (
    <div className="grid gap-8">
      <PageHeader title={t.nav.activity} subtitle={t.activity.subtitle} />

      <div className="grid gap-4 sm:grid-cols-2 lg:max-w-2xl">
        <FormField label={t.activity.person}>
          {(field) => (
            <Select value={filters.person ?? ALL} onValueChange={(person) => update({ person, page: undefined })}>
              <SelectTrigger {...field}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{t.activity.allPeople}</SelectItem>
                {people.data?.map((person) => (
                  <SelectItem key={person.id} value={person.id}>
                    {person.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </FormField>
        <FormField label={t.activity.kind}>
          {(field) => (
            <Select value={filters.kind ?? ALL} onValueChange={(kind) => update({ kind, page: undefined })}>
              <SelectTrigger {...field}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{t.activity.kinds.all}</SelectItem>
                {activityKinds.map((kind) => (
                  <SelectItem key={kind} value={kind}>
                    {t.activity.kinds[kind]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </FormField>
      </div>

      <Card className="py-0">
        {activity.isError ? (
          <ErrorState onRetry={() => activity.refetch()} retrying={activity.isFetching} />
        ) : data && data.total === 0 ? (
          <EmptyState
            icon={HistoryIcon}
            title={filtered ? t.activity.nothingMatches : t.activity.nothingYet}
            action={
              filtered && (
                <Button onClick={() => setParams(new URLSearchParams())}>{t.activity.clearFilters}</Button>
              )
            }
          />
        ) : (
          <>
            <ActivityList items={data?.items ?? []} loading={activity.isPending} loadingRows={8} />
            {data && (
              <nav
                aria-label={t.nav.activity}
                className="flex items-center justify-between gap-4 border-t px-6 py-3"
              >
                <p className="text-sm text-muted-foreground tabular-nums">{t.activity.showing(from, to, data.total)}</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={data.page <= 1}
                    onClick={() => update({ page: String(data.page - 1) })}
                  >
                    {t.common.previous}
                  </Button>
                  <Button
                    size="sm"
                    disabled={data.page >= lastPage}
                    onClick={() => update({ page: String(data.page + 1) })}
                  >
                    {t.common.next}
                  </Button>
                </div>
              </nav>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

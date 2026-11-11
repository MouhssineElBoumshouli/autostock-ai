import { HistoryIcon } from "lucide-react";
import { useSearchParams } from "react-router";

import { type ActivityKind, activityKinds, useActivity, useActivityPeople } from "@/api/activity";
import { ActivityList } from "@/components/ActivityList";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { ALL, FilterChip } from "@/components/FilterChip";
import { PageHeader } from "@/components/PageHeader";
import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { t } from "@/i18n";


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

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.activity} subtitle={t.activity.subtitle} />

      <div className="flex flex-wrap gap-2">
        <FilterChip
          label={t.activity.person}
          value={filters.person}
          allLabel={t.activity.allPeople}
          options={(people.data ?? []).map((person) => ({ value: person.id, label: person.name }))}
          onChange={(person) => update({ person, page: undefined })}
        />
        <FilterChip
          label={t.activity.kind}
          value={filters.kind}
          allLabel={t.activity.kinds.all}
          options={activityKinds.map((kind) => ({ value: kind, label: t.activity.kinds[kind] }))}
          onChange={(kind) => update({ kind, page: undefined })}
        />
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
                <Button onClick={() => setParams(new URLSearchParams())}>{t.common.clearFilters}</Button>
              )
            }
          />
        ) : (
          <>
            <ActivityList items={data?.items ?? []} loading={activity.isPending} loadingRows={8} />
            {data && (
              <Pagination
                page={data.page}
                pageSize={data.page_size}
                total={data.total}
                shown={data.items.length}
                onPage={(page) => update({ page: String(page) })}
              />
            )}
          </>
        )}
      </Card>
    </div>
  );
}

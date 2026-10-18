import { ArrowRightIcon, HistoryIcon } from "lucide-react";
import { Link } from "react-router";

import { useActivity } from "@/api/activity";
import { useStockSummary } from "@/api/stock";
import { useSignedIn } from "@/components/SignedIn";
import { ActivityList } from "@/components/ActivityList";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";
import { LowStockCard } from "@/pages/stock/LowStockCard";
import { StockStats } from "@/pages/stock/StockStats";

function partOfDay(hour: number) {
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

export function HomePage() {
  const me = useSignedIn();
  const canSeeActivity = me.user.role !== "staff";

  return (
    <div className="grid gap-8">
      <PageHeader
        title={t.home.greeting(partOfDay(new Date().getHours()), me.user.name.split(" ")[0])}
        subtitle={me.organization.name}
      />
      <StockOverview />
      {canSeeActivity && <RecentActivity />}
    </div>
  );
}

// Stat cards and the low stock list, once the shop has parts. Nothing is shown before that.
function StockOverview() {
  const summary = useStockSummary();
  if (!summary.data || summary.data.all === 0) return null;
  return (
    <>
      <StockStats summary={summary.data} loading={false} />
      <LowStockCard />
    </>
  );
}

function RecentActivity() {
  const activity = useActivity({ page: 1 });
  const items = activity.data?.items.slice(0, 5) ?? [];

  return (
    <Card className="gap-2 pb-2">
      <CardHeader>
        <CardTitle>{t.home.recentActivity}</CardTitle>
        <CardAction>
          <Button variant="subtle" size="sm" asChild className="-me-3">
            <Link to="/activity">
              {t.home.seeAll}
              <ArrowRightIcon aria-hidden="true" className="rtl:rotate-180" />
            </Link>
          </Button>
        </CardAction>
      </CardHeader>
      {activity.isError ? (
        <ErrorState onRetry={() => activity.refetch()} retrying={activity.isFetching} />
      ) : !activity.isPending && items.length === 0 ? (
        <EmptyState icon={HistoryIcon} title={t.activity.nothingYet} />
      ) : (
        <ActivityList items={items} loading={activity.isPending} />
      )}
    </Card>
  );
}

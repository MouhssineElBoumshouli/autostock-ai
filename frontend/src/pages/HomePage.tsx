import { thingsNeedingYou, useToday } from "@/api/today";
import { useStockSummary } from "@/api/stock";
import { useSignedIn } from "@/components/SignedIn";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { LowStockCard } from "@/pages/stock/LowStockCard";
import { StockStats } from "@/pages/stock/StockStats";

import { LateDeliveriesCard } from "./home/LateDeliveriesCard";
import { NeedsActionCard } from "./home/NeedsActionCard";
import { ToOrderCard } from "./home/ToOrderCard";
import { TodayHeadline } from "./home/TodayHeadline";
import { WeeklySalesCard } from "./home/WeeklySalesCard";
import { WorthALookCard } from "./home/WorthALookCard";

function partOfDay(hour: number) {
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

export function HomePage() {
  const me = useSignedIn();
  const canReview = me.user.role !== "staff";
  const canSeeMoney = me.user.role !== "staff";

  return (
    <div className="grid gap-8">
      <PageHeader
        title={t.home.greeting(partOfDay(new Date().getHours()), me.user.name.split(" ")[0])}
        subtitle={me.organization.name}
      />
      <Today canReview={canReview} canSeeMoney={canSeeMoney} currency={me.organization.currency} />
      <StockOverview />
    </div>
  );
}

function Today({ canReview, canSeeMoney, currency }: { canReview: boolean; canSeeMoney: boolean; currency: string }) {
  const today = useToday();

  if (today.isError) {
    return (
      <Card className="py-0">
        <ErrorState onRetry={() => today.refetch()} retrying={today.isFetching} />
      </Card>
    );
  }

  if (today.isPending) {
    return (
      <div className="grid gap-4" aria-busy="true">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  const data = today.data;
  return (
    // grid-cols-1 (not bare "grid"): without a defined track, a long unbreakable line deep inside
    // (e.g. a truncated part name) can force this whole column wider than the viewport.
    <div className="grid grid-cols-1 gap-6">
      <TodayHeadline count={thingsNeedingYou(data)} />
      <div className="grid gap-4 lg:grid-cols-2">
        <NeedsActionCard alerts={data.needs_action} total={data.needs_action_total} canReview={canReview} />
        <div className="grid gap-4">
          <ToOrderCard toOrder={data.to_order} canSeeMoney={canSeeMoney} currency={currency} />
          <LateDeliveriesCard deliveries={data.late_deliveries} />
        </div>
      </div>
      <WorthALookCard alerts={data.worth_a_look} total={data.worth_a_look_total} />
      <WeeklySalesCard sales={data.weekly_sales} />
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

import { useEffect, useRef, useState } from "react";

import { useForecastsUpdated, useLatestForecastRun, useRunForecastsNow } from "@/api/forecasts";
import { useSignedIn } from "@/components/SignedIn";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatTimeAgo } from "@/lib/format";

// "Forecasts updated 2 hours ago", with an "Update now" button for owners and managers.
// The run itself happens in the background on the server, so this polls for it to finish,
// then refreshes the stock list and part panel so the new numbers show up right away.
export function ForecastStatusBar() {
  const canUpdate = useSignedIn().user.role !== "staff";
  const latest = useLatestForecastRun();
  const runNow = useRunForecastsNow();
  const onUpdated = useForecastsUpdated();
  const [waiting, setWaiting] = useState(false);
  const startedAt = useRef(0);

  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => latest.refetch(), 2000);
    return () => clearInterval(timer);
  }, [waiting, latest]);

  useEffect(() => {
    if (waiting && latest.data && new Date(latest.data.created_at).getTime() >= startedAt.current) {
      setWaiting(false);
      onUpdated();
    }
  }, [waiting, latest.data, onUpdated]);

  function update() {
    startedAt.current = Date.now();
    setWaiting(true);
    runNow.mutate();
  }

  if (latest.isPending) return <Skeleton className="h-5 w-56" />;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-body-medium text-on-surface-variant">
        {latest.data ? t.stock.forecastStatus.updated(formatTimeAgo(latest.data.created_at)) : t.stock.forecastStatus.never}
      </p>
      {canUpdate && (
        <Button variant="outlined" size="sm" loading={waiting || runNow.isPending} onClick={update}>
          {t.stock.forecastStatus.updateNow}
        </Button>
      )}
    </div>
  );
}

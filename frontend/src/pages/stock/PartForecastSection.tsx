import { useState } from "react";

import { type ForecastHorizon, usePartForecast } from "@/api/forecasts";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

import { ForecastChart } from "./ForecastChart";

const HORIZONS: ForecastHorizon[] = [7, 30, 60];

// "What will sell, and when it runs out" for one part: how much over the next 7, 30 or 60 days,
// the range it could really be, a chart of the recent past next to it, and (behind "Show
// details") how the number was made and whether it beat a plain average on this part's own past.
export function PartForecastSection({ partId, branch }: { partId: string; branch?: string }) {
  const forecast = usePartForecast(partId, branch);
  const [horizon, setHorizon] = useState<ForecastHorizon>(7);
  const [showDetails, setShowDetails] = useState(false);

  if (forecast.isError) {
    return <ErrorState onRetry={() => forecast.refetch()} retrying={forecast.isFetching} />;
  }
  if (!forecast.data) {
    return (
      <div className="grid gap-3" aria-busy="true">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const data = forecast.data;
  const current = data.horizons[horizon];

  return (
    <div className="grid gap-3">
      <Tabs value={String(horizon)} onValueChange={(value) => setHorizon(Number(value) as ForecastHorizon)}>
        <TabsList>
          {HORIZONS.map((h) => (
            <TabsTrigger key={h} value={String(h)}>
              {t.part.forecast.tabs[String(h) as keyof typeof t.part.forecast.tabs]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {!current.enough_history ? (
        <p className="text-body-medium text-on-surface-variant">{t.part.forecast.notEnoughHistory}</p>
      ) : (
        <>
          <div>
            <p className="text-display-small tabular-nums">{t.part.forecast.about(formatNumber(current.quantity))}</p>
            <p className="text-body-medium text-on-surface-variant">
              {t.part.forecast.likelyBetween(formatNumber(current.low), formatNumber(current.high))}
            </p>
          </div>

          {data.weeks.length > 0 ? (
            <ForecastChart weeks={data.weeks} horizon={current} />
          ) : (
            <p className="text-body-medium text-on-surface-variant">{t.part.forecast.noSalesYet}</p>
          )}

          <Button variant="text" size="sm" className="justify-self-start" onClick={() => setShowDetails((v) => !v)}>
            {showDetails ? t.part.forecast.hideDetails : t.part.forecast.showDetails}
          </Button>

          {showDetails && (
            <div className="grid gap-1 rounded-md border px-4 py-3 text-body-medium text-on-surface-variant">
              {current.method && <p>{t.part.forecast.methodLabels[current.method]}</p>}
              <p>
                {current.beat_baseline_pct
                  ? t.part.forecast.beatBaseline(String(current.beat_baseline_pct))
                  : t.part.forecast.noBeatBaseline}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

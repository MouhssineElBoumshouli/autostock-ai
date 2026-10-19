import { toast } from "sonner";

import { type CareLevel, careLevels, useOrderSettings, useSaveOrderSettings } from "@/api/orders";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

// Owners only: how big a safety cushion "what to order" suggestions should carry.
export function OrderingCard() {
  const settings = useOrderSettings();
  const save = useSaveOrderSettings();

  function choose(level: CareLevel) {
    if (level === settings.data?.service_target) return;
    save.mutate({ service_target: level }, { onSuccess: () => toast.success(t.orders.settings.saved) });
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{t.orders.settings.title}</CardTitle>
      </CardHeader>
      {settings.isError ? (
        <ErrorState onRetry={() => settings.refetch()} retrying={settings.isFetching} />
      ) : settings.isPending ? (
        <CardContent aria-busy="true">
          <Skeleton className="h-10 w-full" />
        </CardContent>
      ) : (
        <CardContent className="grid gap-3">
          <div className="flex flex-wrap gap-2">
            {careLevels.map((level) => (
              <Button
                key={level}
                type="button"
                variant={settings.data.service_target === level ? "tonal" : "outlined"}
                disabled={save.isPending}
                onClick={() => choose(level)}
              >
                {t.orders.settings.levels[level]}
              </Button>
            ))}
          </div>
          <p className="text-body-small text-on-surface-variant">{t.orders.settings.help[settings.data.service_target]}</p>
        </CardContent>
      )}
    </Card>
  );
}

import { useSetStartHereHidden, useStartHere } from "@/api/startHere";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

// Owners and managers only: bring back the "Start here" checklist after hiding it, or hide it.
// Hidden once every step is already done (nothing left to show or hide).
export function StartHereCard() {
  const startHere = useStartHere();
  const setHidden = useSetStartHereHidden();
  const words = t.settings.startHere;

  if (startHere.data?.all_done) return null;

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{words.title}</CardTitle>
      </CardHeader>
      {startHere.isError ? (
        <ErrorState onRetry={() => startHere.refetch()} retrying={startHere.isFetching} />
      ) : startHere.isPending ? (
        <CardContent aria-busy="true">
          <Skeleton className="h-10 w-full" />
        </CardContent>
      ) : (
        <CardContent className="grid gap-4">
          <p className="text-body-medium text-on-surface-variant">{words.description}</p>
          <div>
            <Button
              variant="outlined"
              loading={setHidden.isPending}
              onClick={() => setHidden.mutate(!startHere.data.hidden)}
            >
              {startHere.data.hidden ? words.show : words.hide}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

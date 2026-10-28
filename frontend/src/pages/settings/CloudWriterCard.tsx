import { toast } from "sonner";

import { useSaveSettings, useSettings } from "@/api/settings";
import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

// Owners only: who writes the "Ask your shop" answers. Off (the default): the app, on this computer.
// On: Groq's free cloud writer, sent only the facts of each answer. Needs GROQ_API_KEY in .env.
export function CloudWriterCard() {
  const settings = useSettings();
  const save = useSaveSettings();
  const words = t.settings.cloudWriter;

  function choose(on: boolean) {
    if (on === settings.data?.cloud_writer_on) return;
    save.mutate({ cloud_writer_on: on }, { onSuccess: () => toast.success(t.settings.saved) });
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{words.title}</CardTitle>
      </CardHeader>
      {settings.isError ? (
        <ErrorState onRetry={() => settings.refetch()} retrying={settings.isFetching} />
      ) : settings.isPending ? (
        <CardContent aria-busy="true">
          <Skeleton className="h-10 w-full" />
        </CardContent>
      ) : (
        <CardContent className="grid gap-3">
          <p className="text-body-medium text-on-surface">{words.description}</p>
          <div className="flex flex-wrap gap-2">
            {[false, true].map((on) => (
              <Button
                key={String(on)}
                type="button"
                variant={settings.data.cloud_writer_on === on ? "tonal" : "outlined"}
                disabled={save.isPending || (on && !settings.data.cloud_writer_ready)}
                onClick={() => choose(on)}
              >
                {on ? words.on : words.off}
              </Button>
            ))}
          </div>
          <p className="text-body-small text-on-surface-variant">{words.note}</p>
          {!settings.data.cloud_writer_ready && <p className="text-body-small text-on-surface-variant">{words.noKey}</p>}
          <FormError message={save.error?.message} />
        </CardContent>
      )}
    </Card>
  );
}

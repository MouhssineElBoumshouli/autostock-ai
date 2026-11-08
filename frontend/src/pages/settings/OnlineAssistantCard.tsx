import { toast } from "sonner";

import { type GroqAllowance, useSaveSettings, useSettings } from "@/api/settings";
import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

// Owners only: the online assistant for the Ask page (Groq, free, needs GROQ_API_KEY in .env). On by default
// once a key is set. Says plainly what is sent, and how much of Groq's free daily allowance is left.
export function OnlineAssistantCard() {
  const settings = useSettings();
  const save = useSaveSettings();
  const words = t.settings.onlineAssistant;

  function choose(on: boolean) {
    if (on === settings.data?.online_assistant_on) return;
    save.mutate({ online_assistant_on: on }, { onSuccess: () => toast.success(t.settings.saved) });
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
                variant={settings.data.online_assistant_on === on ? "tonal" : "outlined"}
                disabled={save.isPending || (on && !settings.data.groq_ready)}
                onClick={() => choose(on)}
              >
                {on ? words.on : words.off}
              </Button>
            ))}
          </div>
          {settings.data.groq_allowance && settings.data.online_assistant_on && (
            <Allowance allowance={settings.data.groq_allowance} />
          )}
          <p className="text-body-small text-on-surface-variant">{words.note}</p>
          {!settings.data.groq_ready && <p className="text-body-small text-on-surface-variant">{words.noKey}</p>}
          <FormError message={save.error?.message} />
        </CardContent>
      )}
    </Card>
  );
}

function Allowance({ allowance }: { allowance: GroqAllowance }) {
  const words = t.settings.onlineAssistant;
  return (
    <div className="grid gap-1 rounded-md bg-surface-container-high p-3 text-body-medium text-on-surface">
      {allowance.answers_left_about !== null && (
        <p>{words.allowance(formatNumber(allowance.answers_left_about), formatNumber(allowance.answers_today))}</p>
      )}
      {allowance.requests_left_today !== null && allowance.requests_per_day !== null && (
        <p className="text-body-small text-on-surface-variant">
          {words.allowanceRequests(formatNumber(allowance.requests_left_today), formatNumber(allowance.requests_per_day))}
        </p>
      )}
    </div>
  );
}

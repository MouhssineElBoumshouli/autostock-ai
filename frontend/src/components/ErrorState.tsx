import { RotateCwIcon, TriangleAlertIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

// Shown when loading failed. Says what happened in plain words and offers "Try again".
export function ErrorState({
  message = t.states.loadFailed,
  onRetry,
  retrying = false,
}: {
  message?: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div role="alert" className="flex flex-col items-center gap-4 px-6 py-12 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-destructive-soft text-destructive">
        <TriangleAlertIcon aria-hidden="true" className="size-6" />
      </span>
      <p className="max-w-sm text-sm text-foreground">{message}</p>
      <Button onClick={onRetry} loading={retrying}>
        <RotateCwIcon aria-hidden="true" />
        {t.common.tryAgain}
      </Button>
    </div>
  );
}

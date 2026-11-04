import { CircleAlertIcon } from "lucide-react";

import type { ImportJob } from "@/api/imports";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { t, translateServerMessage } from "@/i18n";

// The background work stopped. Nothing was saved: it is one transaction.
export function FailedStep({ job, onRestart }: { job: ImportJob; onRestart: () => void }) {
  return (
    <Card>
      <CardContent className="grid gap-6">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-error-container text-on-error-container">
            <CircleAlertIcon aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="text-headline-small" role="alert">
              {t.importFile.failedTitle}
            </h2>
            <p className="text-body-medium text-on-surface-variant">
              {job.preview.file_name} · {job.error && translateServerMessage(job.error)}
            </p>
          </div>
        </div>
        <div>
          <Button variant="filled" onClick={onRestart}>
            {t.importFile.startAgain}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

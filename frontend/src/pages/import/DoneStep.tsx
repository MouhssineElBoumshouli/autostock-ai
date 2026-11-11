import { CircleCheckIcon } from "lucide-react";
import { Link } from "react-router";

import type { ImportKind, ImportSummary } from "@/api/imports";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { t } from "@/i18n";

import { ImportSummaryList } from "./ImportSummaryList";

// Step 4: saved. What was done, and where to go next.
export function DoneStep({ kind, summary, onAnother }: { kind: ImportKind; summary: ImportSummary; onAnother: () => void }) {
  return (
    <Card>
      <CardContent className="grid gap-6">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-full bg-success-container text-on-success-container">
            <CircleCheckIcon aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="text-headline-small" role="status">
              {t.importFile.doneTitle}
            </h2>
            <p className="text-body-medium text-on-surface-variant">
              {summary.file_name} · {t.importFile.kinds[kind].title}
            </p>
          </div>
        </div>
        <ImportSummaryList summary={summary} />
        <div className="flex flex-wrap gap-3">
          <Button variant="filled" asChild>
            <Link to="/stock">{t.importFile.goToStock}</Link>
          </Button>
          <Button onClick={onAnother}>{t.importFile.importAnother}</Button>
        </div>
      </CardContent>
    </Card>
  );
}

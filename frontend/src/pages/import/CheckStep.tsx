import type { ImportKind, ImportSummary } from "@/api/imports";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

import { ImportSummaryList } from "./ImportSummaryList";

// Step 3: what will happen, in plain words, and every row that has a problem. Nothing is saved yet.
export function CheckStep({
  kind,
  summary,
  saving,
  error,
  onBack,
  onSave,
}: {
  kind: ImportKind;
  summary: ImportSummary;
  saving: boolean;
  error?: string;
  onBack: () => void;
  onSave: () => void;
}) {
  const somethingToSave =
    kind === "parts"
      ? summary.counts.new_parts + summary.counts.updated_parts > 0
      : summary.counts.new_sales > 0;
  const hidden = summary.problem_count - summary.problems.length;

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{summary.file_name}</CardTitle>
          <CardDescription>{t.importFile.nothingSaved}</CardDescription>
        </CardHeader>
        <CardContent>
          <ImportSummaryList summary={summary} />
        </CardContent>
      </Card>

      {summary.problem_count > 0 && (
        <Card className="gap-4 pb-0">
          <CardHeader>
            <CardTitle>{t.importFile.problemsTitle}</CardTitle>
            <CardDescription>{t.importFile.problemsText}</CardDescription>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-20 text-end">{t.importFile.row}</TableHead>
                <TableHead>{t.importFile.problem}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summary.problems.map((problem) => (
                <TableRow key={problem.row}>
                  <TableCell className="text-end tabular-nums">{problem.row}</TableCell>
                  <TableCell className="whitespace-normal">{problem.messages.join(" · ")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {hidden > 0 && (
            <p className="border-t px-6 py-3 text-body-medium text-on-surface-variant">
              {t.importFile.moreProblems(formatNumber(hidden))}
            </p>
          )}
        </Card>
      )}

      <Card className="py-4">
        <CardFooter className="flex-wrap justify-between gap-3">
          <Button variant="text" onClick={onBack}>
            {t.common.back}
          </Button>
          <div className="flex flex-wrap items-center justify-end gap-3">
            {!somethingToSave && <p className="text-body-medium text-on-surface-variant">{t.importFile.nothingToSave}</p>}
            <Button variant="filled" disabled={!somethingToSave} loading={saving} onClick={onSave}>
              {t.importFile.save}
            </Button>
          </div>
          <div className="w-full">
            <FormError message={error} />
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}

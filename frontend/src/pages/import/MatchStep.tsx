import { InfoIcon } from "lucide-react";

import type { ImportKind, ImportPreview, Mapping } from "@/api/imports";
import { FormError } from "@/components/FormError";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

const IGNORE = "ignore";

// Step 2: for each column of the file, the person says which field it is (or Ignore).
export function MatchStep({
  kind,
  preview,
  mapping,
  onMapping,
  checking,
  error,
  onBack,
  onNext,
  onUseSalesInstead,
}: {
  kind: ImportKind;
  preview: ImportPreview;
  mapping: Mapping;
  onMapping: (mapping: Mapping) => void;
  checking: boolean;
  error?: string;
  onBack: () => void;
  onNext: () => void;
  // The file looks like sales history, not parts (see preview.looks_like_sales): one click
  // starts the import over with the same file, as "Sales history" instead.
  onUseSalesInstead?: () => void;
}) {
  const names = t.importFile.fieldNames[kind];
  const chosen = Object.values(mapping);
  const missing = preview.fields.filter((field) => field.required && !chosen.includes(field.key));
  const twice = [...new Set(chosen.filter((field, index) => chosen.indexOf(field) !== index))];
  const ready = missing.length === 0 && twice.length === 0;
  const prefilled = Object.keys(preview.mapping).length > 0;

  function choose(column: number, field: string) {
    const next = { ...mapping };
    if (field === IGNORE) delete next[column];
    else next[column] = field;
    onMapping(next);
  }

  return (
    <Card>
      <CardContent className="grid gap-5">
        <p className="text-body-medium text-on-surface-variant">{t.importFile.matchText(formatNumber(preview.row_count))}</p>
        {preview.looks_like_sales && onUseSalesInstead && (
          <p className="flex flex-wrap items-center gap-2 rounded-md bg-tertiary-container px-3 py-2.5 text-body-medium text-on-tertiary-container">
            <InfoIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {t.importFile.looksLikeSales}
            <Button size="sm" variant="tonal" onClick={onUseSalesInstead}>
              {t.importFile.useSalesInstead}
            </Button>
          </p>
        )}
        {prefilled && (
          <p className="flex items-start gap-2 rounded-md bg-secondary-container px-3 py-2.5 text-body-medium text-on-secondary-container">
            <InfoIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {t.importFile.remembered}
          </p>
        )}

        <ul className="grid gap-3">
          {preview.columns.map((column) => {
            const field = mapping[column.index];
            return (
              <li key={column.index} className="grid gap-3 rounded-md border p-4 md:grid-cols-[minmax(0,1fr)_16rem] md:items-start">
                <div className="grid min-w-0 gap-2">
                  <p className="text-title-medium break-words">{column.header}</p>
                  <div>
                    <p className="mb-1 text-body-small text-on-surface-variant">{t.importFile.firstRows}</p>
                    <ul className="flex flex-wrap gap-1.5">
                      {column.samples.map((sample, index) => (
                        <li key={index} className="max-w-48 truncate rounded-sm bg-surface-container-high px-2 py-0.5 text-body-small">
                          {sample || "—"}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <Select value={field ?? IGNORE} onValueChange={(value) => choose(column.index, value)}>
                  <SelectTrigger
                    aria-label={t.importFile.columnField(column.header)}
                    aria-invalid={field !== undefined && twice.includes(field) ? true : undefined}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={IGNORE}>{t.importFile.ignore}</SelectItem>
                    {preview.fields.map((option) => (
                      <SelectItem key={option.key} value={option.key}>
                        {names[option.key]}
                        {option.required && ` (${t.importFile.required})`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </li>
            );
          })}
        </ul>

        <div className="flex flex-wrap items-center gap-2 text-body-medium">
          {preview.fields
            .filter((option) => option.required)
            .map((option) => (
              <Badge key={option.key} variant={chosen.includes(option.key) ? "success" : "warning"}>
                {`${names[option.key]} · ${t.importFile.required}`}
              </Badge>
            ))}
        </div>
        <FormError
          message={
            twice.length > 0
              ? t.importFile.chosenTwice(names[twice[0]])
              : missing.length > 0
                ? t.importFile.stillToMatch(missing.map((option) => names[option.key]).join(", "))
                : error
          }
        />
      </CardContent>
      <CardFooter className="justify-between border-t pt-6">
        <Button variant="text" onClick={onBack}>
          {t.common.back}
        </Button>
        <Button variant="filled" disabled={!ready} loading={checking} onClick={onNext}>
          {t.importFile.checkFile}
        </Button>
      </CardFooter>
    </Card>
  );
}

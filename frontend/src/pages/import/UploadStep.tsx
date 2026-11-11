import { cn } from "cn";
import { FileSpreadsheetIcon } from "lucide-react";
import { useId, useState } from "react";

import { type ImportKind, MAX_IMPORT_BYTES } from "@/api/imports";
import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

const kinds: ImportKind[] = ["parts", "sales", "equivalents"];

function fileProblem(file: File | null): string | undefined {
  if (!file) return t.importFile.noFile;
  if (!/\.(xlsx|csv)$/i.test(file.name)) return t.importFile.wrongType;
  if (file.size > MAX_IMPORT_BYTES) return t.importFile.fileTooBig;
  return undefined;
}

// Step 1: what kind of file, and which file.
export function UploadStep({
  kind,
  file,
  onKind,
  onFile,
  reading,
  error,
  onNext,
}: {
  kind: ImportKind;
  file: File | null;
  onKind: (kind: ImportKind) => void;
  onFile: (file: File | null) => void;
  reading: boolean;
  error?: string;
  onNext: (file: File) => void;
}) {
  const inputId = useId();
  const [showProblem, setShowProblem] = useState(false);
  const problem = fileProblem(file);

  return (
    <Card>
      <CardContent className="grid gap-6">
        <fieldset className="grid gap-3">
          <legend className="mb-1 text-title-small">{t.importFile.kindLabel}</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            {kinds.map((option) => (
              <label
                key={option}
                className={cn(
                  "flex cursor-pointer gap-3 rounded-md border p-4 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary",
                  kind === option ? "border-primary bg-primary/8 shadow-[inset_0_0_0_1px_var(--color-primary)]" : "hover:bg-on-surface/8",
                )}
              >
                <input
                  type="radio"
                  name="kind"
                  value={option}
                  checked={kind === option}
                  onChange={() => onKind(option)}
                  className="mt-1 size-4 accent-primary"
                />
                <span className="grid gap-1">
                  <span className="text-title-small">{t.importFile.kinds[option].title}</span>
                  <span className="text-body-medium text-on-surface-variant">{t.importFile.kinds[option].text}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid gap-2">
          <span className="text-title-small">{t.importFile.fileLabel}</span>
          <label
            htmlFor={inputId}
            className="flex cursor-pointer flex-col items-center gap-3 rounded-md border border-dashed border-outline px-6 py-8 text-center transition-colors hover:bg-on-surface/8 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary"
          >
            <FileSpreadsheetIcon aria-hidden="true" className="size-8 text-on-surface-variant" />
            {file ? (
              <span className="grid gap-0.5">
                <span className="text-title-small break-all">{file.name}</span>
                <span className="text-body-small text-on-surface-variant">
                  {t.importFile.fileSize(formatNumber(Math.ceil(file.size / (1024 * 1024))))} · {t.importFile.changeFile}
                </span>
              </span>
            ) : (
              <span className="text-title-small text-primary">{t.importFile.chooseFile}</span>
            )}
            <span className="text-body-small text-on-surface-variant">{t.importFile.fileHelp}</span>
            <input
              id={inputId}
              type="file"
              accept=".xlsx,.csv"
              className="sr-only"
              onChange={(event) => {
                onFile(event.target.files?.[0] ?? null);
                setShowProblem(true);
              }}
            />
          </label>
        </div>
        {kind !== "equivalents" && (
          <p className="text-body-small text-on-surface-variant">
            {t.importFile.sample.text}{" "}
            <a href={`/api/imports/sample?kind=${kind}`} className="font-medium text-primary underline">
              {kind === "sales" ? t.importFile.sample.sales : t.importFile.sample.parts}
            </a>
          </p>
        )}
        <FormError message={(showProblem && problem) || error} />
      </CardContent>
      <CardFooter className="justify-end border-t pt-6">
        <Button
          variant="filled"
          loading={reading}
          onClick={() => {
            setShowProblem(true);
            if (!problem && file) onNext(file);
          }}
        >
          {t.importFile.readFile}
        </Button>
      </CardFooter>
    </Card>
  );
}

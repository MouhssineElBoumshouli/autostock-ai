import { useState } from "react";
import { useSearchParams } from "react-router";

import {
  type ImportKind,
  type ImportPreview,
  type ImportSummary,
  type Mapping,
  useCheckImport,
  usePreviewImport,
  useSaveImport,
} from "@/api/imports";
import { PageHeader } from "@/components/PageHeader";
import { t } from "@/i18n";

import { CheckStep } from "./CheckStep";
import { DoneStep } from "./DoneStep";
import { MatchStep } from "./MatchStep";
import { type Step, StepList } from "./StepList";
import { UploadStep } from "./UploadStep";

const KINDS: ImportKind[] = ["parts", "sales", "equivalents"];

// Import in four steps. The file stays in the browser and is sent again at each step,
// so leaving the page halfway leaves nothing behind. A link can open it pre-selecting which
// kind of file ("Start here", other screens' empty states): /stock/import?kind=sales.
export function ImportPage() {
  const [params] = useSearchParams();
  const fromLink = params.get("kind");
  const [step, setStep] = useState<Step>("upload");
  const [kind, setKind] = useState<ImportKind>(KINDS.includes(fromLink as ImportKind) ? (fromLink as ImportKind) : "parts");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Mapping>({});
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const previewImport = usePreviewImport();
  const checkImport = useCheckImport();
  const saveImport = useSaveImport();

  function restart() {
    setStep("upload");
    setFile(null);
    setPreview(null);
    setSummary(null);
    previewImport.reset();
    checkImport.reset();
    saveImport.reset();
  }

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.importFile} subtitle={t.importFile.subtitle} />
      <StepList current={step} />

      {step === "upload" && (
        <UploadStep
          kind={kind}
          file={file}
          onKind={setKind}
          onFile={setFile}
          reading={previewImport.isPending}
          error={previewImport.error?.message}
          onNext={(chosen) =>
            previewImport.mutate(
              { file: chosen, kind },
              {
                onSuccess: (result) => {
                  setPreview(result);
                  setMapping(result.mapping);
                  setStep("match");
                },
              },
            )
          }
        />
      )}

      {step === "match" && preview && file && (
        <MatchStep
          kind={kind}
          preview={preview}
          mapping={mapping}
          onMapping={setMapping}
          checking={checkImport.isPending}
          error={checkImport.error?.message}
          onBack={() => setStep("upload")}
          onNext={() =>
            checkImport.mutate(
              { file, kind, mapping },
              {
                onSuccess: (result) => {
                  setSummary(result);
                  setStep("check");
                },
              },
            )
          }
        />
      )}

      {step === "check" && summary && file && (
        <CheckStep
          kind={kind}
          summary={summary}
          saving={saveImport.isPending}
          error={saveImport.error?.message}
          onBack={() => setStep("match")}
          onSave={() =>
            saveImport.mutate(
              { file, kind, mapping },
              {
                onSuccess: (result) => {
                  setSummary(result);
                  setStep("save");
                },
              },
            )
          }
        />
      )}

      {step === "save" && summary && <DoneStep kind={kind} summary={summary} onAnother={restart} />}
    </div>
  );
}

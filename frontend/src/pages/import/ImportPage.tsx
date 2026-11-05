import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import {
  type ImportKind,
  type Mapping,
  useCheckImport,
  useCurrentImport,
  useForgetImport,
  useRefreshAfterImport,
  useSaveImport,
  useUploadImport,
} from "@/api/imports";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";

import { CheckStep } from "./CheckStep";
import { DoneStep } from "./DoneStep";
import { FailedStep } from "./FailedStep";
import { MatchStep } from "./MatchStep";
import { ProgressStep } from "./ProgressStep";
import { type Step, StepList } from "./StepList";
import { UploadStep } from "./UploadStep";

const KINDS: ImportKind[] = ["parts", "sales", "equivalents"];

// Import in four steps. The file stays on the server and the import is followed there, so a page
// reload comes back to the same step, with the same progress bar. A link can open it pre-selecting
// which kind of file ("Start here", other screens' empty states): /stock/import?kind=sales.
export function ImportPage() {
  const [params] = useSearchParams();
  const fromLink = params.get("kind");
  const [kind, setKind] = useState<ImportKind>(KINDS.includes(fromLink as ImportKind) ? (fromLink as ImportKind) : "parts");
  const [file, setFile] = useState<File | null>(null);
  const [editedMapping, setEditedMapping] = useState<Mapping | null>(null);
  const [changingColumns, setChangingColumns] = useState(false);
  const current = useCurrentImport();
  const uploadImport = useUploadImport();
  const checkImport = useCheckImport();
  const saveImport = useSaveImport();
  const forgetImport = useForgetImport();
  const refresh = useRefreshAfterImport();
  const job = current.data ?? null;
  const status = job?.status;

  useEffect(() => {
    if (status === "saved") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  function restart() {
    if (job) forgetImport.mutate(job.id);
    setFile(null);
    setEditedMapping(null);
    setChangingColumns(false);
    uploadImport.reset();
    checkImport.reset();
    saveImport.reset();
  }

  if (current.isPending) {
    return (
      <div className="grid grid-cols-1 gap-8">
        <PageHeader title={t.nav.importFile} subtitle={t.importFile.subtitle} />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (current.isError) return <ErrorState onRetry={() => current.refetch()} retrying={current.isFetching} />;

  const mapping = editedMapping ?? job?.mapping ?? job?.preview.mapping ?? {};
  const matching = status === "uploaded" || (status === "checked" && changingColumns);
  const step: Step = !job || status === "failed" ? "upload" : matching ? "match" : status === "checking" || status === "checked" ? "check" : "save";

  return (
    <div className="grid grid-cols-1 gap-8">
      <PageHeader title={t.nav.importFile} subtitle={t.importFile.subtitle} />
      <StepList current={step} />

      {!job && (
        <UploadStep
          kind={kind}
          file={file}
          onKind={setKind}
          onFile={setFile}
          reading={uploadImport.isPending}
          error={uploadImport.error?.message}
          onNext={(chosen) => uploadImport.mutate({ file: chosen, kind })}
        />
      )}

      {job && matching && (
        <MatchStep
          kind={job.kind}
          preview={job.preview}
          mapping={mapping}
          onMapping={setEditedMapping}
          checking={checkImport.isPending}
          error={checkImport.error?.message}
          onBack={restart}
          onNext={() => {
            setChangingColumns(false);
            checkImport.mutate({ id: job.id, mapping });
          }}
        />
      )}

      {job && (status === "checking" || status === "saving") && <ProgressStep job={job} />}

      {job && status === "checked" && !changingColumns && job.summary && (
        <CheckStep
          kind={job.kind}
          summary={job.summary}
          saving={saveImport.isPending}
          error={saveImport.error?.message}
          onBack={() => setChangingColumns(true)}
          onSave={() => saveImport.mutate(job.id)}
        />
      )}

      {job && status === "saved" && job.summary && <DoneStep kind={job.kind} summary={job.summary} onAnother={restart} />}

      {job && status === "failed" && <FailedStep job={job} onRestart={restart} />}
    </div>
  );
}

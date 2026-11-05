import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type ImportKind = "parts" | "sales" | "equivalents";
export type Mapping = Record<number, string>; // column index -> field

export type ImportPreview = {
  file_name: string;
  row_count: number;
  columns: { index: number; header: string; samples: string[] }[];
  fields: { key: string; required: boolean }[];
  mapping: Mapping;
};

export type ImportSummary = {
  file_name: string;
  counts: Record<string, number>;
  new_suppliers: string[];
  new_branches: string[];
  problems: { row: number; sheet: string | null; messages: string[] }[];
  problem_count: number;
};

export type ImportJob = {
  id: string;
  kind: ImportKind;
  status: "uploaded" | "checking" | "checked" | "saving" | "saved" | "failed";
  rows_done: number;
  rows_total: number;
  finishing: boolean; // every row read, the database is finishing the work
  preview: ImportPreview;
  mapping: Mapping | null;
  summary: ImportSummary | null;
  error: string | null;
};

export const MAX_IMPORT_BYTES = 500 * 1024 * 1024;
const CHECK_EVERY_MS = 1000;

const currentKey = ["import", "current"];

function isRunning(job: ImportJob | null | undefined) {
  return job?.status === "checking" || job?.status === "saving";
}

// The shop's import. It lives on the server, so a page reload finds it again; while it runs in the
// background, this asks how far it got.
export function useCurrentImport() {
  return useQuery({
    queryKey: currentKey,
    queryFn: () => apiRequest<ImportJob | null>("/api/imports/current"),
    refetchInterval: (query) => (isRunning(query.state.data) ? CHECK_EVERY_MS : false),
  });
}

function useJobChange<Input>(request: (input: Input) => Promise<ImportJob>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (job) => queryClient.setQueryData(currentKey, job),
  });
}

export function useUploadImport() {
  return useJobChange(({ file, kind }: { file: File; kind: ImportKind }) => {
    const data = new FormData();
    data.set("file", file);
    data.set("kind", kind);
    return apiRequest<ImportJob>("/api/imports/upload", { method: "POST", body: data });
  });
}

export function useCheckImport() {
  return useJobChange(({ id, mapping }: { id: string; mapping: Mapping }) =>
    apiRequest<ImportJob>(`/api/imports/${id}/check`, { method: "POST", body: { mapping } }),
  );
}

export function useSaveImport() {
  return useJobChange((id: string) => apiRequest<ImportJob>(`/api/imports/${id}/save`, { method: "POST" }));
}

export function useForgetImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/api/imports/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.setQueryData(currentKey, null),
  });
}

// What a finished import changed: the screens showing it read again.
export function useRefreshAfterImport() {
  const queryClient = useQueryClient();
  return () => {
    for (const key of ["stock", "activity", "start-here", "today", "branches", "suppliers"]) {
      queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
}

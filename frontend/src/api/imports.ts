import { useMutation, useQueryClient } from "@tanstack/react-query";

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
  problems: { row: number; messages: string[] }[];
  problem_count: number;
};

export const MAX_IMPORT_BYTES = 10 * 1024 * 1024;

function form(file: File, kind: ImportKind, mapping?: Mapping) {
  const data = new FormData();
  data.set("file", file);
  data.set("kind", kind);
  if (mapping) data.set("mapping", JSON.stringify(mapping));
  return data;
}

// The file is sent again at each step, so nothing half-done stays on the server.
export function usePreviewImport() {
  return useMutation({
    mutationFn: ({ file, kind }: { file: File; kind: ImportKind }) =>
      apiRequest<ImportPreview>("/api/imports/preview", { method: "POST", body: form(file, kind) }),
  });
}

export function useCheckImport() {
  return useMutation({
    mutationFn: ({ file, kind, mapping }: { file: File; kind: ImportKind; mapping: Mapping }) =>
      apiRequest<ImportSummary>("/api/imports/check", { method: "POST", body: form(file, kind, mapping) }),
  });
}

export function useSaveImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, kind, mapping }: { file: File; kind: ImportKind; mapping: Mapping }) =>
      apiRequest<ImportSummary>("/api/imports/save", { method: "POST", body: form(file, kind, mapping) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

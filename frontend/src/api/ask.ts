import { useMutation } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type AskNumberUnit =
  | "pieces"
  | "money"
  | "count"
  | "days"
  | "date"
  | "date_range"
  | "percent"
  | "text"
  | "alert_kind";
// `key` names a fixed label shown in the person's language; without one, `label` is the shop's own words.
export type AskNumber = { label: string; value: number | string; unit: AskNumberUnit; key?: string | null; about?: string | null };
export type AskSuggestion = { question_type: string; label: string; filters: AskFilters; period: string | null };
export type AskFilters = { part?: string; category?: string; branch?: string; period?: string };

export type AskOut = {
  understood: string | null;
  question_type: string;
  filters: AskFilters;
  understood_by: "model" | "rule";
  ai_note: string | null;
  ai_on: boolean;
  period: string | null;
  // `sentence` and `understood` are the server's English; screens build them from these (askSentence.ts).
  key: string;
  values: Record<string, unknown>;
  sentence: string;
  numbers: AskNumber[];
  suggestions: AskSuggestion[];
};

export type AskRequest = { question: string; question_type?: string; filters?: AskFilters };

export function useAsk() {
  return useMutation({
    mutationFn: (body: AskRequest) => apiRequest<AskOut>("/api/ask", { method: "POST", body }),
  });
}

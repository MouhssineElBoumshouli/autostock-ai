import { useMutation } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type AskNumberUnit = "pieces" | "money" | "count" | "days" | "date" | "percent" | "text";
export type AskNumber = { label: string; value: number | string; unit: AskNumberUnit };
export type AskSuggestion = { question_type: string; label: string };
export type AskFilters = { part?: string; category?: string; branch?: string; period?: string };

export type AskOut = {
  understood: string | null;
  question_type: string;
  filters: AskFilters;
  understood_by: "model" | "rule";
  ai_note: string | null;
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

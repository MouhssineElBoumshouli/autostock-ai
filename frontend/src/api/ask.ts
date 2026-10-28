import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError, apiRequest } from "@/api/client";
import { t } from "@/i18n";

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
  // `understood` is the server's English; screens build it from these (askSentence.ts).
  key: string;
  values: Record<string, unknown>;
  // Written by the server in the question's own language (`language`), which may differ from the app's.
  answer: string;
  language: AnswerLanguage;
  numbers: AskNumber[];
  suggestions: AskSuggestion[];
};

export type AnswerLanguage = "en" | "fr" | "ar";

export type AskRequest = { question: string; question_type?: string; filters?: AskFilters };

export function useAsk() {
  return useMutation({
    mutationFn: (body: AskRequest) => apiRequest<AskOut>("/api/ask", { method: "POST", body }),
  });
}

// The assistant (local AI on): one lookup it made, with the real numbers.
export type AssistantLookup = {
  tool: string;
  filters: AskFilters;
  key: string;
  values: Record<string, unknown>;
  numbers: AskNumber[];
};
export type AssistantEvent =
  | { type: "ai_off" }
  | { type: "looking_up"; tool: string; filters: AskFilters }
  | { type: "text"; text: string }
  // The written answer so far is taken back: the cloud writer tries once more, or the app writes it.
  | { type: "restart" }
  // `text` is the answer to show: the app's own (written_by "app"), or the cloud writer's once every
  // sentence passed the check against the shop's data.
  | {
      type: "done";
      text: string;
      written_by: "app" | "cloud";
      language: AnswerLanguage;
      cloud_problems: string[];
      retried: boolean;
      read_by: "rule" | "model" | "follow_up";
      question: AskedBefore | null; // what the app understood; sent back so a follow-up can change it
      lookups: AssistantLookup[];
    };
export type AskedBefore = { type: string; filters: AskFilters };

// Sends the question (and the one before, for follow-ups) and calls `onEvent` for each event as the
// server writes it (newline-delimited JSON).
export async function askAssistant(
  question: string,
  previous: AskedBefore | null,
  onEvent: (event: AssistantEvent) => void,
): Promise<void> {
  const response = await fetch("/api/ask/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, previous }),
  });
  if (!response.ok || !response.body) throw new ApiError(response.status, t.states.somethingWrong);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let waiting = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    waiting += value;
    const lines = waiting.split("\n");
    waiting = lines.pop() ?? "";
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line) as AssistantEvent);
  }
  if (waiting.trim()) onEvent(JSON.parse(waiting) as AssistantEvent);
}

// Each person's last questions and answers, kept on the server.
export type AskedEntry =
  | { id: string; question: string; kind: "assistant"; answer: Extract<AssistantEvent, { type: "done" }> }
  | { id: string; question: string; kind: "rule"; answer: AskOut };

export function useAskHistory() {
  return useQuery({
    queryKey: ["ask", "history"],
    queryFn: () => apiRequest<AskedEntry[]>("/api/ask/history"),
    staleTime: Infinity, // read once per visit: the page keeps the newer ones itself
  });
}

export function forgetAskHistory() {
  return apiRequest<void>("/api/ask/history", { method: "DELETE" });
}

export function useAiOn() {
  return useQuery({
    queryKey: ["ask", "ai"],
    queryFn: () => apiRequest<{ ai_on: boolean }>("/api/ask/ai"),
    staleTime: 60_000,
  });
}

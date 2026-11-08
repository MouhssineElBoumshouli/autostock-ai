import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { meQueryKey } from "@/api/auth";
import { apiRequest } from "@/api/client";
import type { Language } from "@/i18n";

export const currencies = ["MAD", "EUR", "USD"] as const;
export type Currency = (typeof currencies)[number];
export type ShopSettings = {
  name: string;
  currency: Currency;
  language: Language;
  online_assistant_on: boolean;
  groq_ready: boolean; // a Groq key is in .env: only then can the online assistant work
  groq_allowance: GroqAllowance | null;
};
// What is left of Groq's free daily allowance (backend/app/ask/allowance.py). Nulls: not known yet.
export type GroqAllowance = {
  tokens_used_today: number;
  tokens_per_day: number | null;
  answers_today: number;
  answers_left_about: number | null;
  requests_left_today: number | null;
  requests_per_day: number | null;
};
export type SettingsChange = Partial<Pick<ShopSettings, "name" | "currency" | "language" | "online_assistant_on">>;

const settingsQueryKey = ["settings"];

export function useSettings() {
  return useQuery({ queryKey: settingsQueryKey, queryFn: () => apiRequest<ShopSettings>("/api/settings") });
}

export function useSaveSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (change: SettingsChange) => apiRequest<ShopSettings>("/api/settings", { method: "PATCH", body: change }),
    onSuccess: (settings) => {
      queryClient.setQueryData(settingsQueryKey, settings);
      // The shop name is shown in the top bar.
      queryClient.invalidateQueries({ queryKey: meQueryKey });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

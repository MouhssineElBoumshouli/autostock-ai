import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { meQueryKey } from "@/api/auth";
import { apiRequest } from "@/api/client";
import type { Language } from "@/i18n";

export const currencies = ["MAD", "EUR", "USD"] as const;
export type Currency = (typeof currencies)[number];
export type ShopSettings = { name: string; currency: Currency; language: Language };

const settingsQueryKey = ["settings"];

export function useSettings() {
  return useQuery({ queryKey: settingsQueryKey, queryFn: () => apiRequest<ShopSettings>("/api/settings") });
}

export function useSaveSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: ShopSettings) => apiRequest<ShopSettings>("/api/settings", { method: "PATCH", body: settings }),
    onSuccess: (settings) => {
      queryClient.setQueryData(settingsQueryKey, settings);
      // The shop name is shown in the top bar.
      queryClient.invalidateQueries({ queryKey: meQueryKey });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

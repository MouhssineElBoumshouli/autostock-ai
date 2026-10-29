import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type StepKey = "branches" | "import_parts" | "import_sales" | "suppliers" | "team";
export type StartHereStep = { key: StepKey; done: boolean };
export type StartHere = { hidden: boolean; all_done: boolean; steps: StartHereStep[] };

const startHereQueryKey = ["start-here"];

export function useStartHere() {
  return useQuery({ queryKey: startHereQueryKey, queryFn: () => apiRequest<StartHere>("/api/start-here") });
}

export function useSetStartHereHidden() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (hidden: boolean) => apiRequest<StartHere>("/api/start-here", { method: "PATCH", body: { hidden } }),
    onSuccess: (data) => queryClient.setQueryData(startHereQueryKey, data),
  });
}

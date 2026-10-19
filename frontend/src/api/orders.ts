import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type SuggestionStatus = "suggested" | "cut_by_budget" | "approved" | "rejected";
export type SuggestionRule = "forecast" | "slow_out_of_stock" | "slow_skip";

export type OrderLine = {
  id: string;
  part_id: string;
  part_sku: string;
  part_name: string;
  branch_id: string;
  branch_name: string;
  supplier_id: string | null;
  supplier_name: string | null;
  status: SuggestionStatus;
  rule: SuggestionRule;
  quantity: number;
  approved_quantity: number | null;
  on_hand: number;
  on_order: number;
  pack_size: number;
  delivery_days: number;
  days_covered: number;
  expected: number;
  cushion: number;
  need: number;
  unit_cost: number | null;
  line_cost: number;
  missed_sales_prevented: number;
  value_per_dirham: number | null;
  reason: string;
};

export type OrderRun = {
  id: string;
  created_at: string;
  history_last_day: string | null;
  budget: number | null;
  suggested_cost: number;
  kept_cost: number;
  kept_lines: number;
  cut_lines: number;
  lines: OrderLine[];
};

export const runQueryKey = ["orders", "latest"];

export function useLatestRun() {
  return useQuery({ queryKey: runQueryKey, queryFn: () => apiRequest<OrderRun | null>("/api/orders/suggestions/latest") });
}

export function useCreateSuggestions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (budget: number | null) => apiRequest<OrderRun>("/api/orders/suggestions", { method: "POST", body: { budget } }),
    onSuccess: (run) => queryClient.setQueryData(runQueryKey, run),
  });
}

export function useDecideLine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, quantity }: { id: string; decision: "approve" | "reject"; quantity?: number }) =>
      apiRequest<OrderLine>(`/api/orders/suggestions/${id}/decide`, { method: "POST", body: { decision, quantity } }),
    onSuccess: (line) => {
      queryClient.setQueryData<OrderRun | null>(runQueryKey, (run) =>
        run ? { ...run, lines: run.lines.map((row) => (row.id === line.id ? line : row)) } : run,
      );
      queryClient.invalidateQueries({ queryKey: ["purchaseOrders"] });
    },
  });
}

export function useApproveAllForSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, supplierId }: { runId: string; supplierId: string }) =>
      apiRequest<OrderLine[]>(`/api/orders/runs/${runId}/suppliers/${supplierId}/approve-all`, { method: "POST" }),
    onSuccess: (approved) => {
      const byId = new Map(approved.map((line) => [line.id, line]));
      queryClient.setQueryData<OrderRun | null>(runQueryKey, (run) =>
        run ? { ...run, lines: run.lines.map((row) => byId.get(row.id) ?? row) } : run,
      );
      queryClient.invalidateQueries({ queryKey: ["purchaseOrders"] });
    },
  });
}

export const careLevels = [0.8, 0.9, 0.95] as const;
export type CareLevel = (typeof careLevels)[number];
export type OrderSettings = { service_target: CareLevel };

const orderSettingsQueryKey = ["orders", "settings"];

export function useOrderSettings() {
  return useQuery({ queryKey: orderSettingsQueryKey, queryFn: () => apiRequest<OrderSettings>("/api/orders/settings") });
}

export function useSaveOrderSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: OrderSettings) => apiRequest<OrderSettings>("/api/orders/settings", { method: "PATCH", body: settings }),
    onSuccess: (settings) => queryClient.setQueryData(orderSettingsQueryKey, settings),
  });
}

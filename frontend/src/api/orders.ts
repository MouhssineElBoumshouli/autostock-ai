import { keepPreviousData, type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
  sold_last_90_days: number;
  unit_cost: number | null;
  line_cost: number;
  missed_sales_prevented: number;
  value_per_dirham: number | null;
  reason: string; // English; screens show orderReason(line) instead
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
  groups: OrderGroup[]; // most urgent first, the lines cut by the budget last
};

// One supplier's lines, or the lines with no supplier ("none"), or the lines cut by the budget ("didnt_fit").
export type OrderGroup = {
  key: string;
  supplier_id: string | null;
  supplier_name: string | null;
  line_count: number;
  pending_count: number;
  total_cost: number;
};

export type OrderLinesPage = { items: OrderLine[]; total: number; page: number; page_size: number };

export const runQueryKey = ["orders", "latest"];
const linesQueryKey = ["orders", "lines"];

// After a decision or a delivery: the supplier totals and the lines both changed.
export function refreshOrderRun(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: runQueryKey });
  queryClient.invalidateQueries({ queryKey: linesQueryKey });
}

export function useLatestRun() {
  return useQuery({ queryKey: runQueryKey, queryFn: () => apiRequest<OrderRun | null>("/api/orders/suggestions/latest") });
}

// One group's lines, 50 at a time: a big shop has tens of thousands.
export function useRunLines(runId: string, group: string, page: number) {
  return useQuery({
    queryKey: [...linesQueryKey, runId, group, page],
    queryFn: () =>
      apiRequest<OrderLinesPage>(`/api/orders/runs/${runId}/lines?group=${encodeURIComponent(group)}&page=${page}`),
    placeholderData: keepPreviousData,
  });
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
      queryClient.setQueriesData<OrderLinesPage>({ queryKey: linesQueryKey }, (page) =>
        page ? { ...page, items: page.items.map((row) => (row.id === line.id ? line : row)) } : page,
      );
      queryClient.invalidateQueries({ queryKey: runQueryKey });
      queryClient.invalidateQueries({ queryKey: ["purchaseOrders"] });
    },
  });
}

export function useApproveAllForSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, supplierId }: { runId: string; supplierId: string }) =>
      apiRequest<{ approved: number }>(`/api/orders/runs/${runId}/suppliers/${supplierId}/approve-all`, { method: "POST" }),
    onSuccess: () => {
      refreshOrderRun(queryClient);
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

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type AlertGroup = "needs_action" | "worth_a_look";
export type AlertStatus = "open" | "looked_at" | "not_a_problem";

export type Alert = {
  id: string;
  kind: string;
  group: AlertGroup;
  part_id: string;
  part_name: string;
  sku: string;
  branch_name: string;
  sentence: string;
  numbers: Record<string, unknown>;
  money_at_stake?: number; // absent for staff: the server leaves it out entirely
  started_on: string;
  raised_on: string;
  status: AlertStatus;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
};

export type AlertFilters = { status?: AlertStatus; group?: AlertGroup };

export function useAlerts(filters: AlertFilters) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.group) params.set("group", filters.group);
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: () => apiRequest<Alert[]>(`/api/alerts?${params}`),
  });
}

export function useReviewAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: "looked_at" | "not_a_problem" }) =>
      apiRequest<Alert>(`/api/alerts/${id}/review`, { method: "POST", body: { status } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["today"] });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

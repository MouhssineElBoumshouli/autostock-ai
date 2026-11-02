import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { refreshOrderRun } from "@/api/orders";

export type PurchaseOrderStatus = "draft" | "sent" | "received";

export type PurchaseOrderLine = {
  id: string;
  part_id: string;
  part_sku: string;
  part_name: string;
  branch_id: string;
  branch_name: string;
  quantity: number;
  received_quantity: number;
  unit_cost: number | null;
  line_cost: number;
};

export type PurchaseOrderSummary = {
  id: string;
  order_number: string;
  status: PurchaseOrderStatus;
  created_at: string;
  sent_at: string | null;
  received_at: string | null;
  supplier_id: string;
  supplier_name: string;
  total_cost: number;
  line_count: number;
};

export type PurchaseOrder = PurchaseOrderSummary & {
  supplier_phone: string | null;
  supplier_email: string | null;
  lines: PurchaseOrderLine[];
};

const listQueryKey = ["purchaseOrders"];
const detailQueryKey = (id: string) => ["purchaseOrders", id];

export function usePurchaseOrders() {
  return useQuery({ queryKey: listQueryKey, queryFn: () => apiRequest<PurchaseOrderSummary[]>("/api/orders/purchase-orders") });
}

export function usePurchaseOrder(id: string | null) {
  return useQuery({
    queryKey: detailQueryKey(id ?? ""),
    queryFn: () => apiRequest<PurchaseOrder>(`/api/orders/purchase-orders/${id}`),
    enabled: id !== null,
  });
}

export function useSendPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<PurchaseOrder>(`/api/orders/purchase-orders/${id}/send`, { method: "POST" }),
    onSuccess: (po) => {
      queryClient.setQueryData(detailQueryKey(po.id), po);
      queryClient.invalidateQueries({ queryKey: listQueryKey });
    },
  });
}

export function useReceivePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, lines }: { id: string; lines: Record<string, number> }) =>
      apiRequest<PurchaseOrder>(`/api/orders/purchase-orders/${id}/receive`, { method: "POST", body: { lines } }),
    onSuccess: (po) => {
      queryClient.setQueryData(detailQueryKey(po.id), po);
      queryClient.invalidateQueries({ queryKey: listQueryKey });
      refreshOrderRun(queryClient);
      queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}

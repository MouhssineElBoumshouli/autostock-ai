import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import type { StockStatus } from "@/components/StockBadge";

export type StockSummary = { all: number; healthy: number; low: number; out: number };
export type Choice = { id: string; name: string };
export type StockFilterChoices = { categories: string[]; branches: Choice[]; suppliers: Choice[] };

export type PartRow = {
  id: string;
  sku: string;
  name: string;
  brand: string | null;
  category: string | null;
  quantity: number;
  min_stock: number;
  status: StockStatus;
  supplier: string | null;
};
export type PartsPage = { items: PartRow[]; total: number; page: number; page_size: number };

export const statusFilters = ["healthy", "low", "out", "dead", "inactive"] as const;
export type StatusFilter = (typeof statusFilters)[number];
export type SortKey = "name" | "sku" | "brand" | "quantity" | "min_stock" | "status" | "supplier";

export type PartsQuery = {
  search?: string;
  status?: StatusFilter;
  category?: string;
  branch?: string;
  supplier?: string;
  sort?: SortKey;
  direction: "asc" | "desc";
  page: number;
};

export type PartDetail = {
  id: string;
  sku: string;
  name: string;
  brand: string | null;
  category: string | null;
  oem_reference: string | null;
  unit_cost: number | null;
  sale_price: number | null;
  min_stock: number;
  is_active: boolean;
  quantity: number;
  status: StockStatus;
  supplier: { id: string; name: string; phone: string | null; email: string | null; delivery_days: number | null } | null;
  stock: { branch_id: string; branch: string; quantity: number }[];
  last_sales: { sold_on: string; branch: string; quantity: number; unit_price: number | null }[];
};

export type PartChange = Partial<{
  name: string;
  brand: string | null;
  category: string | null;
  oem_reference: string | null;
  unit_cost: number | null;
  sale_price: number | null;
  min_stock: number;
  supplier_id: string | null;
  is_active: boolean;
  stock: { branch_id: string; quantity: number }[];
}>;

export function useStockSummary() {
  return useQuery({ queryKey: ["stock", "summary"], queryFn: () => apiRequest<StockSummary>("/api/stock/summary") });
}

export function useStockFilterChoices() {
  return useQuery({
    queryKey: ["stock", "filters"],
    queryFn: () => apiRequest<StockFilterChoices>("/api/stock/filters"),
  });
}

export function useParts(query: PartsQuery) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return useQuery({
    queryKey: ["stock", "parts", query],
    queryFn: () => apiRequest<PartsPage>(`/api/stock/parts?${params}`),
    placeholderData: keepPreviousData,
  });
}

export function usePart(id: string | null) {
  return useQuery({
    queryKey: ["stock", "part", id],
    queryFn: () => apiRequest<PartDetail>(`/api/parts/${id}`),
    enabled: id !== null,
  });
}

export function useChangePart(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (change: PartChange) => apiRequest<PartDetail>(`/api/parts/${id}`, { method: "PATCH", body: change }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

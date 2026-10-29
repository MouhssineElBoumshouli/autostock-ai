import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type Supplier = {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  delivery_days: number | null;
  in_use: boolean;
};

export type SupplierDetails = { phone: string | null; email: string | null; delivery_days: number | null };

const suppliersQueryKey = ["suppliers"];

export function useSuppliers() {
  return useQuery({ queryKey: suppliersQueryKey, queryFn: () => apiRequest<Supplier[]>("/api/suppliers") });
}

export function useAddSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string } & SupplierDetails) => apiRequest<Supplier>("/api/suppliers", { method: "POST", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: suppliersQueryKey }),
  });
}

export function useRenameSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiRequest<Supplier>(`/api/suppliers/${id}`, { method: "PATCH", body: { name } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: suppliersQueryKey }),
  });
}

export function useSaveSupplierDetails() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & SupplierDetails) =>
      apiRequest<Supplier>(`/api/suppliers/${id}/details`, { method: "PATCH", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: suppliersQueryKey }),
  });
}

export function useMergeSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, into }: { id: string; into: string }) =>
      apiRequest<void>(`/api/suppliers/${id}/merge`, { method: "POST", body: { into } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: suppliersQueryKey });
      queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}

export function useRemoveSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/api/suppliers/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: suppliersQueryKey }),
  });
}

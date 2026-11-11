import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type Branch = { id: string; name: string; in_use: boolean };

const branchesQueryKey = ["branches"];

export function useBranches() {
  return useQuery({ queryKey: branchesQueryKey, queryFn: () => apiRequest<Branch[]>("/api/branches") });
}

export function useRenameBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiRequest<Branch>(`/api/branches/${id}`, { method: "PATCH", body: { name } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: branchesQueryKey }),
  });
}

export function useMergeBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, into }: { id: string; into: string }) =>
      apiRequest<void>(`/api/branches/${id}/merge`, { method: "POST", body: { into } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: branchesQueryKey });
      queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}

export function useRemoveBranch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/api/branches/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: branchesQueryKey }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type Role = "owner" | "manager" | "staff";
export const roles: Role[] = ["owner", "manager", "staff"];

export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
};

const usersQueryKey = ["users"];

export function useUsers() {
  return useQuery({ queryKey: usersQueryKey, queryFn: () => apiRequest<User[]>("/api/users") });
}

export type NewUser = { name: string; email: string; role: Role; temporary_password: string };

export function useAddUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (user: NewUser) => apiRequest<User>("/api/users", { method: "POST", body: user }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usersQueryKey }),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, temporary_password }: { id: string; temporary_password: string }) =>
      apiRequest<void>(`/api/users/${id}/password`, { method: "POST", body: { temporary_password } }),
  });
}

export function useChangeUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...change }: { id: string; role?: Role; is_active?: boolean }) =>
      apiRequest<User>(`/api/users/${id}`, { method: "PATCH", body: change }),
    // The change may affect the logged-in person too (e.g. an owner stepping down).
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

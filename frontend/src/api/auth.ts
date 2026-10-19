import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiRequest } from "@/api/client";
import type { User } from "@/api/users";

export type Me = { user: User; organization: { id: string; name: string; currency: string; is_demo: boolean } };

export const meQueryKey = ["me"];

// The logged-in person, or null when nobody is logged in.
export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<Me | null> => {
      try {
        return await apiRequest<Me>("/api/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function useSetupNeeded() {
  return useQuery({
    queryKey: ["setup"],
    queryFn: async () => (await apiRequest<{ needed: boolean }>("/api/setup")).needed,
  });
}

export type SetupForm = { shop_name: string; name: string; email: string; password: string };

export function useSetup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: SetupForm) => apiRequest<Me>("/api/setup", { method: "POST", body: form }),
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
      queryClient.setQueryData(["setup"], false);
    },
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: { email: string; password: string }) =>
      apiRequest<Me>("/api/auth/login", { method: "POST", body: form }),
    onSuccess: (me) => queryClient.setQueryData(meQueryKey, me),
  });
}

export function useChangePassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: { current_password: string; new_password: string }) =>
      apiRequest<Me>("/api/auth/password", { method: "POST", body: form }),
    onSuccess: (me) => queryClient.setQueryData(meQueryKey, me),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest<void>("/api/auth/logout", { method: "POST" }),
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}

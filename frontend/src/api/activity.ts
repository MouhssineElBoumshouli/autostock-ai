import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type PersonRef = { id: string; name: string };

export type ActivityItem = {
  id: string;
  created_at: string;
  action: string;
  entity: string;
  actor: PersonRef | null;
  target: PersonRef | null;
  before: Record<string, string | boolean> | null;
  after: Record<string, string | boolean> | null;
};

export type ActivityPage = { items: ActivityItem[]; total: number; page: number; page_size: number };

export const activityKinds = ["team", "passwords", "logins", "settings"] as const;
export type ActivityKind = (typeof activityKinds)[number];

export type ActivityFilters = { page: number; person?: string; kind?: ActivityKind };

export function useActivity(filters: ActivityFilters) {
  const query = new URLSearchParams({ page: String(filters.page) });
  if (filters.person) query.set("person", filters.person);
  if (filters.kind) query.set("kind", filters.kind);
  return useQuery({
    queryKey: ["activity", filters],
    queryFn: () => apiRequest<ActivityPage>(`/api/activity?${query}`),
    // Keeps the current page on screen while the next one loads.
    placeholderData: keepPreviousData,
  });
}

export function useActivityPeople() {
  return useQuery({ queryKey: ["activity", "people"], queryFn: () => apiRequest<PersonRef[]>("/api/activity/people") });
}

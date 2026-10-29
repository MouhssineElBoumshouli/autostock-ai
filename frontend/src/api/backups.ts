import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type BackupProblem = "disk_full" | "database_unreachable" | "failed";

// Owners only. `on` is false while developing: there are no backups then.
export type Backups = {
  on: boolean;
  last_good_at: string | null;
  kept: number;
  problem: BackupProblem | null;
};

export function useBackups() {
  return useQuery({ queryKey: ["backups"], queryFn: () => apiRequest<Backups>("/api/backups") });
}

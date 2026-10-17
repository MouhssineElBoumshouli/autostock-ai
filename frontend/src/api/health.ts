import { useQuery } from "@tanstack/react-query";

type HealthResponse = {
  status: "ok";
  database: "reachable" | "unreachable";
};

export type ServerState = "connected" | "databaseDown" | "serverDown";

// Never throws: a failed check is an answer ("serverDown"), not an error.
// This keeps the badge steady instead of flashing "Checking…" on every re-check.
async function checkServer(): Promise<ServerState> {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) return "serverDown";
    const health: HealthResponse = await response.json();
    return health.database === "reachable" ? "connected" : "databaseDown";
  } catch {
    return "serverDown";
  }
}

// Checks every 10 seconds, so the badge updates by itself if the server stops or comes back.
export function useServerState() {
  return useQuery({
    queryKey: ["health"],
    queryFn: checkServer,
    refetchInterval: 10_000,
  });
}

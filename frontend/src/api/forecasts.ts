import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

export type ForecastRun = {
  trigger: "manual" | "sales_import";
  status: "done" | "failed";
  seconds: number;
  series_count: number;
  history_last_day: string | null;
  created_at: string;
};

export type ForecastMethod =
  | "four_week_average"
  | "last_week"
  | "exponential_smoothing"
  | "croston"
  | "sba"
  | "tsb"
  | "boosting";

export type HorizonForecast = {
  enough_history: boolean;
  quantity: number;
  low: number;
  high: number;
  method: ForecastMethod | null;
  beat_baseline_pct: number | null;
};

export type ForecastHorizon = 7 | 30 | 60;

export type PartForecast = {
  weeks: { week_start: string; quantity: number }[];
  horizons: Record<ForecastHorizon, HorizonForecast>;
};

export function useLatestForecastRun() {
  return useQuery({
    queryKey: ["forecasts", "latest"],
    queryFn: () => apiRequest<ForecastRun | null>("/api/forecasts/runs/latest"),
  });
}

export function useRunForecastsNow() {
  return useMutation({
    mutationFn: () => apiRequest<{ status: string }>("/api/forecasts/run", { method: "POST" }),
  });
}

// Invalidated once a forecast run started here has finished, so the stock list and part panel
// pick up the fresh numbers without the person having to reload the page themselves.
export function useForecastsUpdated() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["forecasts"] });
    queryClient.invalidateQueries({ queryKey: ["stock"] });
  };
}

export function usePartForecast(partId: string | null, branch?: string) {
  const params = branch ? `?branch=${branch}` : "";
  return useQuery({
    queryKey: ["forecasts", "part", partId, branch],
    queryFn: () => apiRequest<PartForecast>(`/api/forecasts/part/${partId}${params}`),
    enabled: partId !== null,
  });
}

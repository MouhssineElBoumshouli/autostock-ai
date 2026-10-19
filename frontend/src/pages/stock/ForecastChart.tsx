import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";

import type { HorizonForecast } from "@/api/forecasts";
import { t } from "@/i18n";
import { formatMonthDay, formatNumber } from "@/lib/format";

type ChartRow = { label: string; actual?: number; base?: number; belowPoint?: number; abovePoint?: number; tooltip: string };

// The last 12 weeks actually sold, as solid violet bars, then the forecast as one bar in the
// same violet: solid from "low" up to the point estimate, lighter from there up to "high" — so
// the likely range is drawn, not just said in text, and never the amber/orange used for warnings.
// Weekly totals only: the forecast itself is one number for its whole horizon, so it gets one bar.
export function ForecastChart({ weeks, horizon }: { weeks: { week_start: string; quantity: number }[]; horizon: HorizonForecast }) {
  const rows: ChartRow[] = [
    ...weeks.map((week) => ({
      label: formatMonthDay(week.week_start),
      actual: week.quantity,
      tooltip: `${t.part.forecast.chartSold}: ${formatNumber(week.quantity)}`,
    })),
    {
      label: t.part.forecast.chartForecast,
      base: horizon.low,
      belowPoint: Math.max(horizon.quantity - horizon.low, 0),
      abovePoint: Math.max(horizon.high - horizon.quantity, 0),
      tooltip: t.part.forecast.likelyBetween(formatNumber(horizon.low), formatNumber(horizon.high)),
    },
  ];

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={rows} margin={{ top: 4, right: 28, bottom: 0, left: 4 }} barCategoryGap={4}>
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={{ stroke: "var(--color-outline-variant)" }}
          tick={{ fontSize: 10, fill: "var(--color-on-surface-variant)" }}
          tickFormatter={(value: string, index: number) => (index % 3 === 0 || index === rows.length - 1 ? value : "")}
          interval={0}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--color-on-surface)", opacity: 0.06 }} />
        <Bar dataKey="actual" fill="var(--color-primary)" radius={[2, 2, 0, 0]} maxBarSize={20} />
        <Bar dataKey="base" stackId="forecast" fill="transparent" />
        <Bar dataKey="belowPoint" stackId="forecast" fill="var(--color-primary)" fillOpacity={0.55} maxBarSize={20} />
        <Bar dataKey="abovePoint" stackId="forecast" fill="var(--color-primary)" fillOpacity={0.2} radius={[2, 2, 0, 0]} maxBarSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartRow }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-sm bg-inverse-surface px-3 py-2 text-body-small text-inverse-on-surface shadow-elevation-2">
      <p className="font-medium">{row.label}</p>
      <p>{row.tooltip}</p>
    </div>
  );
}

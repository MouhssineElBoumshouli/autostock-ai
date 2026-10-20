import { Bar, BarChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis } from "recharts";

import type { WeekPoint } from "@/api/today";
import { t } from "@/i18n";
import { formatMonthDay, formatNumber } from "@/lib/format";

type ChartRow = { label: string; quantity: number };

// 12 weeks of total sales, with a line at the normal week (the baseline) for easy comparison.
export function WeeklySalesChart({ weeks, normal }: { weeks: WeekPoint[]; normal: number }) {
  const rows: ChartRow[] = weeks.map((week) => ({ label: formatMonthDay(week.week_start), quantity: week.quantity }));

  return (
    // min-w-0 so this shrinks inside the card's flex column instead of forcing it wider, and
    // overflow-hidden as a safety net for ResponsiveContainer's own first-measurement hiccups.
    <div className="min-w-0 overflow-hidden">
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 4 }} barCategoryGap={4}>
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={{ stroke: "var(--color-outline-variant)" }}
            tick={{ fontSize: 10, fill: "var(--color-on-surface-variant)" }}
            tickFormatter={(value: string, index: number) => (index % 3 === 0 || index === rows.length - 1 ? value : "")}
            interval={0}
          />
          <ReferenceLine y={normal} stroke="var(--color-outline)" strokeDasharray="4 4" />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--color-on-surface)", opacity: 0.06 }} />
          <Bar dataKey="quantity" fill="var(--color-primary)" radius={[2, 2, 0, 0]} maxBarSize={24} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartRow }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-sm bg-inverse-surface px-3 py-2 text-body-small text-inverse-on-surface shadow-elevation-2">
      <p className="font-medium">{row.label}</p>
      <p>
        {t.part.forecast.chartSold}: {formatNumber(row.quantity)}
      </p>
    </div>
  );
}

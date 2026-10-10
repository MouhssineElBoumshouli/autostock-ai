import {
  Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatDate, formatQuantity, type DemandPoint } from '@/lib/dashboard'

export default function ForecastPlot({ data, uom }: { data: DemandPoint[]; uom: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 9, right: 13, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#edf0f5" strokeDasharray="3 4" vertical={false} />
        <XAxis dataKey="date" tickFormatter={(value: string) => formatDate(value)} tickLine={false} axisLine={false} minTickGap={35} tick={{ fill: '#8b93a2', fontSize: 9 }} />
        <YAxis width={32} tickLine={false} axisLine={false} allowDecimals={false} tick={{ fill: '#8b93a2', fontSize: 9 }} />
        <Tooltip
          labelFormatter={(value: unknown) => formatDate(String(value), { year: 'numeric' })}
          formatter={(value: unknown, name: unknown) => [
            `${formatQuantity(Number(value))} ${uom}`,
            name === 'actual' ? 'Delivered' : name === 'forecast' ? 'Forecast' : name === 'range' ? 'Uncertainty range' : 'Lower range',
          ]}
          contentStyle={{ border: '1px solid #e7e9f0', borderRadius: 10, boxShadow: '0 8px 25px #1c27410f', fontSize: 10 }}
        />
        <Area dataKey="floor" stackId="interval" stroke="none" fill="transparent" isAnimationActive={false} legendType="none" tooltipType="none" />
        <Area dataKey="range" stackId="interval" stroke="none" fill="#e8e3ff" fillOpacity={0.78} isAnimationActive={false} legendType="none" />
        <Line dataKey="actual" type="monotone" stroke="#9ca4b1" strokeWidth={1.7} dot={false} connectNulls isAnimationActive={false} />
        <Line dataKey="forecast" type="monotone" stroke="#7656e8" strokeWidth={2.5} dot={false} connectNulls isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

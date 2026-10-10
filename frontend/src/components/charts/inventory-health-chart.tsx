import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { formatQuantity } from '@/lib/dashboard'

type HealthCategory = { key: string; label: string; count: number }

export default function InventoryHealthChart({ categories, colors }: { categories: HealthCategory[]; colors: Record<string, string> }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={categories} dataKey="count" nameKey="label" innerRadius={53} outerRadius={72} paddingAngle={2} stroke="none" isAnimationActive={false}>
          {categories.map((item) => <Cell key={item.key} fill={colors[item.key]} />)}
        </Pie>
        <Tooltip formatter={(value: unknown) => [formatQuantity(Number(value), 0), 'Parts']} contentStyle={{ border: '1px solid #e7e9f0', borderRadius: 9, fontSize: 10 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

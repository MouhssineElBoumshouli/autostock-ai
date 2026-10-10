import type { ForecastRun } from '@/api/contracts'

export type DemandPoint = {
  date: string
  actual: number | null
  forecast: number | null
  floor: number | null
  range: number | null
}

export function combineDemandHistory(forecast: ForecastRun): DemandPoint[] {
  const history: DemandPoint[] = forecast.history.map((item) => ({
    date: item.date,
    actual: item.units,
    forecast: null,
    floor: null,
    range: null,
  }))
  const future: DemandPoint[] = forecast.predictions.map((item) => ({
    date: item.date,
    actual: null,
    forecast: item.units,
    floor: item.lower,
    range: Math.max(0, item.upper - item.lower),
  }))

  if (history.length && future.length) {
    future[0] = { ...future[0], actual: history.at(-1)?.actual ?? null }
  }
  return [...history, ...future]
}

export function formatQuantity(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value)
}

export function formatDate(value: string, options: Intl.DateTimeFormatOptions = {}): string {
  const date = new Date(`${value}T12:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', ...options }).format(date)
}

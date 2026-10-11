import type { ForecastDetailData } from '@/api/contracts'

export type ForecastChartPoint = {
  date: string
  actual: number | null
  forecast: number | null
  lower: number | null
  band: number | null
  returns: number | null
  events: number | null
  future: boolean
  forecastAnchor?: boolean
}

/** Present the saved total as an estimate without implying precision the source does not support. */
export function formatEmployeeForecastTotal(value: number, rounding: number, uom: string) {
  let scaled = rounding
  let decimalPlaces = 0
  while (decimalPlaces < 6 && Math.abs(scaled - Math.round(scaled)) > 1e-8) {
    scaled *= 10
    decimalPlaces += 1
  }
  const amount = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimalPlaces,
  }).format(value)
  return `About ${amount} ${uom} expected`
}

type ForecastChartInput = Pick<ForecastDetailData['run'], 'observations' | 'predictions'>

/**
 * Build the chart series without changing any saved future forecast values.
 * The last historical value anchors the forecast line so the two series join
 * continuously; its range remains absent because it is observed history.
 */
export function buildForecastChartPoints(run: ForecastChartInput): ForecastChartPoint[] {
  const history: ForecastChartPoint[] = run.observations.map((item) => ({
    date: item.day,
    actual: item.delivered_units,
    forecast: null,
    lower: null,
    band: null,
    returns: item.returned_units,
    events: item.source_event_count,
    future: false,
  }))
  const predictions: ForecastChartPoint[] = run.predictions.map((item) => ({
    date: item.day,
    actual: null,
    forecast: item.units,
    lower: item.lower_heuristic,
    band: Math.max(0, item.upper_heuristic - item.lower_heuristic),
    returns: null,
    events: null,
    future: true,
  }))

  const lastHistoryPoint = history.at(-1)
  if (lastHistoryPoint && predictions.length && lastHistoryPoint.actual !== null) {
    lastHistoryPoint.forecast = lastHistoryPoint.actual
    lastHistoryPoint.forecastAnchor = true
  }

  return [...history, ...predictions]
}

type ParsedForecastDate = { date: Date; isCalendarDate: boolean }

function isValidCalendarDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  if (!Number.isInteger(year) || month < 1 || month > 12 || day < 1) return false
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  return day <= daysInMonth
}

function parseForecastDate(value: string): ParsedForecastDate | null {
  const source = value.trim()
  const datePart = source.match(/^(\d{4}-\d{2}-\d{2})(?:$|[ T])/)
  if (!datePart || !isValidCalendarDate(datePart[1])) return null

  if (/^\d{4}-\d{2}-\d{2}$/.test(source)) {
    // A date-only value is a calendar day, not a UTC instant; keep its label
    // stable instead of shifting it across midnight for extreme time zones.
    return { date: new Date(`${source}T12:00:00Z`), isCalendarDate: true }
  }

  if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$/i.test(source)) return null
  const normalized = source.includes('T') ? source : source.replace(' ', 'T')
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const date = new Date(hasZone ? normalized : `${normalized}Z`)
  return Number.isNaN(date.getTime()) ? null : { date, isCalendarDate: false }
}

function formatForecastValue(value: string, timezone: string, options: Intl.DateTimeFormatOptions) {
  const parsed = parseForecastDate(value)
  if (!parsed) return 'Date unavailable'
  try {
    return new Intl.DateTimeFormat(undefined, {
      timeZone: parsed.isCalendarDate ? 'UTC' : timezone,
      ...options,
    }).format(parsed.date)
  } catch {
    return 'Date unavailable'
  }
}

export function formatForecastDate(value: string, timezone: string, options: Intl.DateTimeFormatOptions = {}) {
  return formatForecastValue(value, timezone, {
    month: 'short',
    day: 'numeric',
    ...options,
  })
}

export function formatForecastDateTime(value: string, timezone: string) {
  return formatForecastValue(value, timezone, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatForecastTime(value: string, timezone: string) {
  return formatForecastValue(value, timezone, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

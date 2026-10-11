import { describe, expect, it } from 'vitest'
import { buildForecastChartPoints, formatForecastDate, formatForecastDateTime, formatForecastTime } from './forecasts'

describe('forecast chart data', () => {
  it('keeps the first saved prediction and its heuristic range distinct from the last actual', () => {
    const points = buildForecastChartPoints({
      observations: [{
        day: '2026-09-26', delivered_units: 5, returned_units: 0,
        units: 5, source_event_count: 2,
      }],
      predictions: [{ day: '2026-09-27', units: 2, lower_heuristic: 1, upper_heuristic: 4 }],
    })

    expect(points).toHaveLength(2)
    expect(points[0]).toMatchObject({
      date: '2026-09-26', actual: 5, forecast: 5, lower: null,
      band: null, future: false, forecastAnchor: true,
    })
    expect(points[1]).toMatchObject({
      date: '2026-09-27', actual: null, forecast: 2, lower: 1,
      band: 3, future: true,
    })
    expect(points[1].forecast).not.toBe(points[0].actual)
  })

  it('keeps every future point equal to the saved forecast, including a one-day run', () => {
    const predictions = [
      { day: '2026-09-27', units: 2, lower_heuristic: 1, upper_heuristic: 4 },
      { day: '2026-09-28', units: 6, lower_heuristic: 3, upper_heuristic: 8 },
    ]
    const points = buildForecastChartPoints({
      observations: [{ day: '2026-09-26', delivered_units: 5, returned_units: 0, units: 5, source_event_count: 1 }],
      predictions: [predictions[0]],
    })
    expect(points.filter((point) => point.future).map((point) => ({
      date: point.date, units: point.forecast, lower: point.lower, upper: (point.lower ?? 0) + (point.band ?? 0),
    }))).toEqual([{ date: '2026-09-27', units: 2, lower: 1, upper: 4 }])

    const allPoints = buildForecastChartPoints({
      observations: [{ day: '2026-09-26', delivered_units: 5, returned_units: 0, units: 5, source_event_count: 1 }],
      predictions,
    })
    expect(allPoints.filter((point) => point.future).map((point) => point.forecast)).toEqual([2, 6])
  })
})

describe('forecast date formatting', () => {
  const timezone = 'Africa/Casablanca'

  it('formats Odoo UTC datetimes in the session timezone', () => {
    const timestamp = '2026-09-27 14:20:00'
    const instant = new Date('2026-09-27T14:20:00Z')
    expect(formatForecastDate(timestamp, timezone, { year: 'numeric' })).toBe(
      new Intl.DateTimeFormat(undefined, { timeZone: timezone, month: 'short', day: 'numeric', year: 'numeric' }).format(instant),
    )
    expect(formatForecastDateTime(timestamp, timezone)).toBe(
      new Intl.DateTimeFormat(undefined, { timeZone: timezone, month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }).format(instant),
    )
    expect(formatForecastTime(timestamp, timezone)).toBe(
      new Intl.DateTimeFormat(undefined, { timeZone: timezone, hour: 'numeric', minute: '2-digit' }).format(instant),
    )
  })

  it('formats ISO datetimes with an explicit offset and without one', () => {
    const explicitOffset = '2026-09-27T16:20:00+02:00'
    const naiveIso = '2026-09-27T14:20:00'
    expect(formatForecastDateTime(explicitOffset, timezone)).toBe(formatForecastDateTime('2026-09-27T14:20:00Z', timezone))
    expect(formatForecastDateTime(naiveIso, timezone)).toBe(formatForecastDateTime('2026-09-27 14:20:00', timezone))
  })

  it('preserves date-only calendar labels and handles invalid values gracefully', () => {
    expect(formatForecastDate('2026-09-27', 'Pacific/Kiritimati', { year: 'numeric' })).toBe(
      new Intl.DateTimeFormat(undefined, { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' }).format(new Date('2026-09-27T12:00:00Z')),
    )
    expect(formatForecastDate('2026-02-31', timezone)).toBe('Date unavailable')
    expect(formatForecastDateTime('not a date', timezone)).toBe('Date unavailable')
  })
})

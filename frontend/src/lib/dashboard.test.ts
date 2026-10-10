import { describe, expect, it } from 'vitest'
import type { ForecastRun } from '@/api/contracts'
import { combineDemandHistory, formatDate, formatQuantity } from './dashboard'

const sampleRun = {
  id: 7,
  product_name: 'Front Brake Rotor',
  sku: 'BRK-440',
  warehouse_name: 'Central warehouse',
  horizon_days: 30,
  uom: 'Units',
  source_type: 'synthetic_demo',
  source_label: 'Synthetic demo',
  review_status: 'reviewed',
  evaluation_status: 'baseline_only',
  history_start: '2026-08-01',
  history_end: '2026-08-03',
  history: [
    { date: '2026-08-01', units: 2 },
    { date: '2026-08-02', units: 4 },
    { date: '2026-08-03', units: 1 },
  ],
  predictions: [
    { date: '2026-08-04', units: 3, lower: 1, upper: 5 },
    { date: '2026-08-05', units: 2, lower: 0, upper: 4 },
  ],
  limitations: 'Planning estimate only.',
} satisfies ForecastRun

describe('dashboard display helpers', () => {
  it('joins real history and forecast without changing observed values', () => {
    const points = combineDemandHistory(sampleRun)

    expect(points).toHaveLength(5)
    expect(points[2]).toMatchObject({ actual: 1, forecast: null })
    expect(points[3]).toMatchObject({ actual: 1, forecast: 3, floor: 1, range: 4 })
  })

  it('handles forecasts without history or projections', () => {
    expect(combineDemandHistory({ ...sampleRun, history: [], predictions: [] })).toEqual([])
  })

  it('formats quantities and dates for readable labels', () => {
    expect(formatQuantity(1200)).toBe('1,200')
    expect(formatDate('not-a-date')).toBe('not-a-date')
  })
})

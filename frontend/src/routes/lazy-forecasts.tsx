import { lazy, Suspense } from 'react'
import { useParams } from '@tanstack/react-router'

const ForecastsPage = lazy(() => import('@/routes/forecasts').then((module) => ({ default: module.ForecastsPage })))
const ForecastDetailPage = lazy(() => import('@/routes/forecasts').then((module) => ({ default: module.ForecastDetailPage })))

export function LazyForecastsRoute() {
  return <Suspense fallback={<main className="route-loading" role="status">Opening your forecasts…</main>}><ForecastsPage /></Suspense>
}

export function LazyForecastDetailRoute() {
  const { runId } = useParams({ from: '/forecasts/$runId' })
  return <Suspense fallback={<main className="route-loading" role="status">Opening forecast details…</main>}><ForecastDetailPage runId={Number(runId)} /></Suspense>
}

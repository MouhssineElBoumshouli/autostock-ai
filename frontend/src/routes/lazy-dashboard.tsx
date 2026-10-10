import { lazy, Suspense } from 'react'

const DashboardPage = lazy(() => import('@/routes/dashboard').then((module) => ({ default: module.DashboardPage })))

export function LazyDashboardRoute() {
  return (
    <Suspense fallback={<main className="route-loading" role="status">Opening your AutoStock workspace…</main>}>
      <DashboardPage />
    </Suspense>
  )
}

import { lazy, Suspense } from 'react'

const InventoryPage = lazy(() => import('@/routes/inventory').then((module) => ({ default: module.InventoryPage })))

export function LazyInventoryRoute() {
  return (
    <Suspense fallback={<main className="route-loading" role="status">Opening your inventory…</main>}>
      <InventoryPage />
    </Suspense>
  )
}

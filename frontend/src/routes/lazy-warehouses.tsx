import { lazy, Suspense } from 'react'
import { useParams } from '@tanstack/react-router'

const WarehousesPage = lazy(() => import('@/routes/warehouses').then((module) => ({ default: module.WarehousesPage })))
const WarehouseDetailPage = lazy(() => import('@/routes/warehouses').then((module) => ({ default: module.WarehouseDetailPage })))

export function LazyWarehousesRoute() {
  return (
    <Suspense fallback={<main className="route-loading" role="status">Opening your warehouses…</main>}>
      <WarehousesPage />
    </Suspense>
  )
}

export function LazyWarehouseDetailRoute() {
  const { warehouseId } = useParams({ from: '/warehouses/$warehouseId' })
  return (
    <Suspense fallback={<main className="route-loading" role="status">Opening warehouse details…</main>}>
      <WarehouseDetailPage warehouseId={Number(warehouseId)} />
    </Suspense>
  )
}

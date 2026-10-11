import { lazy, Suspense } from 'react'
import { useParams } from '@tanstack/react-router'

const LazySuppliersPage = lazy(() => import('@/routes/suppliers').then((module) => ({ default: module.SuppliersPage })))
const LazySupplierDetailPage = lazy(() => import('@/routes/suppliers').then((module) => ({ default: module.SupplierDetailPage })))
const LazySupplierGapsPage = lazy(() => import('@/routes/suppliers').then((module) => ({ default: module.SupplierGapsPage })))

export function LazySuppliersRoute() {
  return <Suspense fallback={<main className="route-loading" role="status">Opening your suppliers…</main>}><LazySuppliersPage /></Suspense>
}

export function LazySupplierGapsRoute() {
  return <Suspense fallback={<main className="route-loading" role="status">Opening parts without a supplier…</main>}><LazySupplierGapsPage /></Suspense>
}

export function LazySupplierDetailRoute() {
  const { supplierId } = useParams({ from: '/suppliers/$supplierId' })
  return <Suspense fallback={<main className="route-loading" role="status">Opening supplier details…</main>}><LazySupplierDetailPage supplierId={Number(supplierId)} /></Suspense>
}

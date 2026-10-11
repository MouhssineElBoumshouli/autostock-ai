import { createRootRoute, createRoute, createRouter, Outlet } from '@tanstack/react-router'
import { LazyDashboardRoute } from '@/routes/lazy-dashboard'
import { LazyInventoryRoute } from '@/routes/lazy-inventory'
import { LazyWarehouseDetailRoute, LazyWarehousesRoute } from '@/routes/lazy-warehouses'
import { LazySupplierDetailRoute, LazySupplierGapsRoute, LazySuppliersRoute } from '@/routes/lazy-suppliers'

const rootRoute = createRootRoute({ component: Outlet })
const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LazyDashboardRoute,
})
const inventoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/inventory',
  component: LazyInventoryRoute,
})
const warehousesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/warehouses',
  component: LazyWarehousesRoute,
})
const warehouseDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/warehouses/$warehouseId',
  component: LazyWarehouseDetailRoute,
})
const suppliersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/suppliers',
  component: LazySuppliersRoute,
})
const supplierGapsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/suppliers/missing',
  component: LazySupplierGapsRoute,
})
const supplierDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/suppliers/$supplierId',
  component: LazySupplierDetailRoute,
})

export const router = createRouter({ routeTree: rootRoute.addChildren([dashboardRoute, inventoryRoute, warehousesRoute, warehouseDetailRoute, suppliersRoute, supplierGapsRoute, supplierDetailRoute]) })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

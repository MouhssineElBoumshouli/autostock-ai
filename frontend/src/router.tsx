import { createRootRoute, createRoute, createRouter, Outlet } from '@tanstack/react-router'
import { LazyDashboardRoute } from '@/routes/lazy-dashboard'
import { LazyInventoryRoute } from '@/routes/lazy-inventory'

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

export const router = createRouter({ routeTree: rootRoute.addChildren([dashboardRoute, inventoryRoute]) })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

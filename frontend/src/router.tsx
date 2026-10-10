import { createRootRoute, createRoute, createRouter, Outlet } from '@tanstack/react-router'
import { LazyDashboardRoute } from '@/routes/lazy-dashboard'

const rootRoute = createRootRoute({ component: Outlet })
const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LazyDashboardRoute,
})

export const router = createRouter({ routeTree: rootRoute.addChildren([dashboardRoute]) })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

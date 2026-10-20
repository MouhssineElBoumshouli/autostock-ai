import type { ReactNode } from "react";
import { createBrowserRouter, type RouteObject } from "react-router";

import { RequireLogin } from "@/components/RequireLogin";
import { RequireRole } from "@/components/RequireRole";
import { AppShell } from "@/components/shell/AppShell";
import type { PageHandle } from "@/components/shell/navigation";
import { ActivityPage } from "@/pages/ActivityPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { ChangePasswordPage } from "@/pages/ChangePasswordPage";
import { DesignPage } from "@/pages/design/DesignPage";
import { HomePage } from "@/pages/HomePage";
import { ImportPage } from "@/pages/import/ImportPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OrdersPage } from "@/pages/orders/OrdersPage";
import { PurchaseOrderPrintPage } from "@/pages/orders/PurchaseOrderPrintPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SetupPage } from "@/pages/SetupPage";
import { StockPage } from "@/pages/stock/StockPage";
import { TeamPage } from "@/pages/team/TeamPage";

// The /design page is a tool for building screens, so it only exists while developing. It is public.
const developmentRoutes: RouteObject[] = import.meta.env.DEV ? [{ path: "/design", element: <DesignPage /> }] : [];

function page(path: string, element: ReactNode, title: PageHandle["title"]): RouteObject {
  return { path, element, handle: { title } satisfies PageHandle };
}

export const router = createBrowserRouter([
  // Outside the app frame: first-time setup, login, and the design page.
  { path: "/setup", element: <SetupPage /> },
  { path: "/login", element: <LoginPage /> },
  ...developmentRoutes,
  {
    element: <RequireLogin />,
    children: [
      // The printable purchase order page: no sidebar or top bar, so printing only shows the order.
      { path: "/orders/purchase-orders/:id/print", element: <PurchaseOrderPrintPage /> },
      {
        element: <AppShell />,
        children: [
          page("/", <HomePage />, "home"),
          page("/alerts", <AlertsPage />, "alerts"),
          page("/change-password", <ChangePasswordPage />, "changePassword"),
          page("/stock", <StockPage />, "stock"),
          page("/orders", <OrdersPage />, "orders"),
          {
            element: <RequireRole roles={["owner", "manager"]} />,
            children: [page("/activity", <ActivityPage />, "activity"), page("/stock/import", <ImportPage />, "importFile")],
          },
          {
            element: <RequireRole roles={["owner"]} />,
            children: [page("/team", <TeamPage />, "team"), page("/settings", <SettingsPage />, "settings")],
          },
          page("*", <NotFoundPage />, "notFound"),
        ],
      },
    ],
  },
]);

import { createBrowserRouter } from "react-router";

import { DesignPage } from "@/pages/design/DesignPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

// The /design page is a tool for building screens, so it only exists while developing.
const developmentRoutes = import.meta.env.DEV ? [{ path: "/design", element: <DesignPage /> }] : [];

export const router = createBrowserRouter([
  { path: "/", element: <HomePage /> },
  ...developmentRoutes,
  { path: "*", element: <NotFoundPage /> },
]);

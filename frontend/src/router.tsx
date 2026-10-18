import { createBrowserRouter } from "react-router";

import { RequireLogin } from "@/components/RequireLogin";
import { ChangePasswordPage } from "@/pages/ChangePasswordPage";
import { DesignPage } from "@/pages/design/DesignPage";
import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { SetupPage } from "@/pages/SetupPage";
import { TeamPage } from "@/pages/team/TeamPage";

// The /design page is a tool for building screens, so it only exists while developing. It is public.
const developmentRoutes = import.meta.env.DEV ? [{ path: "/design", element: <DesignPage /> }] : [];

export const router = createBrowserRouter([
  { path: "/setup", element: <SetupPage /> },
  { path: "/login", element: <LoginPage /> },
  ...developmentRoutes,
  {
    element: <RequireLogin />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/change-password", element: <ChangePasswordPage /> },
      { element: <RequireLogin roles={["owner"]} />, children: [{ path: "/team", element: <TeamPage /> }] },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

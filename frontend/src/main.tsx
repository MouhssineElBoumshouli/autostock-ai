import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Direction } from "radix-ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router/dom";

import { Toaster } from "@/components/ui/sonner";
import { direction, locale } from "@/i18n";
import { router } from "@/router";

const queryClient = new QueryClient();

document.documentElement.lang = locale;
document.documentElement.dir = direction;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Direction.Provider dir={direction}>
        <RouterProvider router={router} />
        <Toaster />
      </Direction.Provider>
    </QueryClientProvider>
  </StrictMode>,
);

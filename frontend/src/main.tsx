import "./index.css";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Direction } from "radix-ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router/dom";

import { meQueryKey } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Toaster } from "@/components/ui/sonner";
import { direction, locale } from "@/i18n";
import { router } from "@/router";

// If the server says "please log in" (e.g. the session expired), forget who was logged in.
// The login guard then sends the person to the login page.
function forgetLoginWhenExpired(error: Error) {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(meQueryKey, null);
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: forgetLoginWhenExpired }),
  mutationCache: new MutationCache({ onError: forgetLoginWhenExpired }),
  defaultOptions: {
    // Retry only when the server could not answer, not when it said no.
    queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 },
  },
});

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

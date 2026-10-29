import "./index.css";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Direction } from "radix-ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router/dom";

import { meQueryKey } from "@/api/auth";
import { ApiError, apiRequest } from "@/api/client";
import { ConnectionLostBanner } from "@/components/ConnectionLostBanner";
import { Snackbar } from "@/components/ui/snackbar";
import { direction, language } from "@/i18n";
import { noteFailure, noteSuccess } from "@/lib/connectionStatus";
import { setShopUtcOffsetMinutes } from "@/lib/format";
import { router } from "@/router";

// The shop's own offset from UTC (not this computer's), so every time shown on a page is right
// even on a browser whose own time zone data is older than 20 Sep 2026. See lib/format.ts.
apiRequest<{ utc_offset_minutes: number }>("/api/shop-time")
  .then(({ utc_offset_minutes }) => setShopUtcOffsetMinutes(utc_offset_minutes))
  .catch(() => {}); // the default (0) is already right for Morocco; worth trying again isn't worth blocking the app for

// If the server says "please log in" (e.g. the session expired), forget who was logged in.
// The login guard then sends the person to the login page.
function forgetLoginWhenExpired(error: Error) {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(meQueryKey, null);
  }
  noteFailure(error);
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: forgetLoginWhenExpired }),
  mutationCache: new MutationCache({ onError: forgetLoginWhenExpired }),
  defaultOptions: {
    // Retry only when the server could not answer, not when it said no.
    queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 },
  },
});
// Any request succeeding again is "connection lost" going away -- the banner disappears by itself.
queryClient.getQueryCache().subscribe((event) => {
  if (event.type === "updated" && event.query.state.status === "success") noteSuccess();
});
queryClient.getMutationCache().subscribe((event) => {
  if (event.type === "updated" && event.mutation.state.status === "success") noteSuccess();
});

document.documentElement.lang = language;
document.documentElement.dir = direction;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Direction.Provider dir={direction}>
        <RouterProvider router={router} />
        <Snackbar />
        <ConnectionLostBanner />
      </Direction.Provider>
    </QueryClientProvider>
  </StrictMode>,
);

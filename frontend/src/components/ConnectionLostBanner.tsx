import { useSyncExternalStore } from "react";

import { t } from "@/i18n";
import { connectionTroubleSnapshot, subscribeConnectionTrouble } from "@/lib/connectionStatus";

// A thin bar across the top while the server can't be reached. It goes away by itself, the
// moment any request succeeds again (main.tsx) -- nothing typed on the page is ever touched.
export function ConnectionLostBanner() {
  const trouble = useSyncExternalStore(subscribeConnectionTrouble, connectionTroubleSnapshot);
  if (!trouble) return null;

  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-50 bg-error-container px-4 py-2 text-center text-body-medium text-on-error-container"
    >
      {t.states.connectionLost}
    </div>
  );
}

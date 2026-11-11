import { createContext, useContext } from "react";

import type { Me } from "@/api/auth";

// The logged-in person, handed down by RequireLogin to every private page.
// Pages read it from here (not from the server query directly), so after logging out
// nothing tries to draw a person who is no longer there.
export const SignedInContext = createContext<Me | null>(null);

export function useSignedIn(): Me {
  const me = useContext(SignedInContext);
  if (!me) throw new Error("useSignedIn is only for pages inside RequireLogin.");
  return me;
}

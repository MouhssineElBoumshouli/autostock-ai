import { ApiError } from "@/api/client";

// Whether the app currently seems unable to reach the server: no response at all (the fetch
// itself threw) or the server answered with its own problem (5xx). A plain "no" (401, 404, a
// validation error...) is not connection trouble -- the server is reached and answering fine.
let trouble = false;
const listeners = new Set<() => void>();

function set(next: boolean): void {
  if (next === trouble) return;
  trouble = next;
  for (const listen of listeners) listen();
}

export function noteFailure(error: unknown): void {
  if (!(error instanceof ApiError) || error.status >= 500) set(true);
}

export function noteSuccess(): void {
  set(false);
}

export function subscribeConnectionTrouble(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function connectionTroubleSnapshot(): boolean {
  return trouble;
}

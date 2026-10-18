import { t } from "@/i18n";

// An error from the server, with its plain-words message ready to show.
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

// The one way the website talks to the server. Cookies are sent automatically.
export async function apiRequest<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await readMessage(response));
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

async function readMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    // Our own errors carry a sentence; validation errors from the framework carry a list.
    return typeof body.detail === "string" ? body.detail : t.states.somethingWrong;
  } catch {
    return t.states.somethingWrong;
  }
}

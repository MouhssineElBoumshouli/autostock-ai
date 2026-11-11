import { t } from "@/i18n";

// Quick checks in the browser so people see mistakes before sending. The server checks again.

export function requiredError(value: string): string | undefined {
  return value.trim() ? undefined : t.validation.required;
}

export function emailError(value: string): string | undefined {
  const [local, domain = ""] = value.trim().split("@");
  if (!value.trim()) return t.validation.required;
  return local && domain.includes(".") ? undefined : t.validation.email;
}

export function passwordError(value: string): string | undefined {
  return value.length >= 10 ? undefined : t.validation.passwordLength;
}

// Only follow "next" links that stay on this website.
export function safeNextPath(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

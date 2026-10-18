import { CircleAlertIcon } from "lucide-react";

// A message about the whole form (not one field), e.g. "Wrong email or password."
export function FormError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="flex items-start gap-2 rounded-lg bg-destructive-soft px-3 py-2.5 text-sm font-medium text-destructive"
    >
      <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {message}
    </p>
  );
}

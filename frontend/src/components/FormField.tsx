import { CircleAlertIcon } from "lucide-react";
import { type ReactNode, useId } from "react";

export type FieldControlProps = {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
};

// Material 3 outlined field: the label sits in a gap of the top border, supporting text and
// error text below, all linked to the control for screen readers.
// The gap is painted in --field-bg, which cards, dialogs and sheets set to their own color.
// Usage: <FormField label="Part name">{(field) => <Input {...field} />}</FormField>
export function FormField({
  label,
  help,
  error,
  children,
}: {
  label: string;
  help?: string;
  error?: string;
  children: (field: FieldControlProps) => ReactNode;
}) {
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const describedBy = [help && helpId, error && errorId].filter(Boolean).join(" ");

  return (
    <div className="group grid gap-1">
      <div className="relative">
        {children({
          id,
          "aria-describedby": describedBy || undefined,
          "aria-invalid": error ? true : undefined,
        })}
        <label
          htmlFor={id}
          className="pointer-events-none absolute start-3 top-0 -translate-y-1/2 bg-(--field-bg,var(--color-surface)) px-1 text-body-small text-on-surface-variant group-focus-within:text-primary group-has-aria-invalid:text-error"
        >
          {label}
        </label>
      </div>
      {help && (
        <p id={helpId} className="px-4 text-body-small text-on-surface-variant">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} className="flex items-center gap-1.5 px-4 text-body-small text-error">
          <CircleAlertIcon aria-hidden="true" className="size-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}

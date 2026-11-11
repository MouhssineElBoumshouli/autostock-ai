import { useId } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

// A checkbox with its label on the side and optional help text underneath.
export function CheckboxField({
  label,
  help,
  checked,
  onCheckedChange,
}: {
  label: string;
  help?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const id = useId();
  const helpId = `${id}-help`;

  return (
    <div className="flex items-start gap-3">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
        aria-describedby={help ? helpId : undefined}
        className="mt-px"
      />
      <div className="grid gap-1">
        <Label htmlFor={id}>{label}</Label>
        {help && (
          <p id={helpId} className="text-body-small text-on-surface-variant">
            {help}
          </p>
        )}
      </div>
    </div>
  );
}

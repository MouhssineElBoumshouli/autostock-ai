import { cn } from "cn";
import { CheckIcon } from "lucide-react";
import { Checkbox as CheckboxPrimitive } from "radix-ui";
import type * as React from "react";

// Material 3 checkbox: 18px box, 2px corners, filled with the primary color when checked.
function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        // The ::after area makes the box easier to tap on a phone.
        "peer relative flex size-[18px] shrink-0 items-center justify-center rounded-[2px] border-2 border-on-surface-variant transition-colors after:absolute after:-inset-3 hover:border-on-surface disabled:cursor-not-allowed disabled:opacity-38 aria-invalid:border-error data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-on-primary",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator data-slot="checkbox-indicator">
        <CheckIcon aria-hidden="true" className="size-3.5" strokeWidth={3.5} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };

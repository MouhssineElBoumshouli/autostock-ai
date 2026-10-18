import { cn } from "cn";
import type * as React from "react";

// Material 3 outlined text field. The label sits on the border (see FormField).
// 16px text so iPhones do not zoom in when the field is tapped.
const fieldClasses =
  "h-14 w-full min-w-0 rounded-xs border border-outline bg-transparent px-4 text-body-large text-on-surface transition-[border-color,box-shadow] placeholder:text-on-surface-variant/70 hover:border-on-surface focus-visible:border-primary focus-visible:shadow-[inset_0_0_0_1px_var(--color-primary)] focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-38 aria-invalid:border-error aria-invalid:focus-visible:shadow-[inset_0_0_0_1px_var(--color-error)]";

function Input({ className, type = "text", ...props }: React.ComponentProps<"input">) {
  return <input type={type} data-slot="input" className={cn(fieldClasses, className)} {...props} />;
}

export { fieldClasses, Input };

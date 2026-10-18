import { cn } from "cn";
import type * as React from "react";

// Text is 16px on phones so iPhones do not zoom in when the field is tapped.
const fieldClasses =
  "h-10 w-full min-w-0 rounded-lg border border-input bg-card px-3 text-base shadow-xs transition-colors placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive md:text-sm";

function Input({ className, type = "text", ...props }: React.ComponentProps<"input">) {
  return <input type={type} data-slot="input" className={cn(fieldClasses, className)} {...props} />;
}

export { fieldClasses, Input };

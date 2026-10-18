import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";
import type * as React from "react";

// A status label on a tonal container (8px corners), with a dot.
const badgeVariants = cva(
  "inline-flex h-6 w-fit shrink-0 items-center gap-1.5 rounded-sm px-2 text-label-medium whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "bg-surface-container-highest text-on-surface-variant",
        success: "bg-success-container text-on-success-container",
        warning: "bg-warning-container text-on-warning-container",
        error: "bg-error-container text-on-error-container",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

// The word is required: color alone never carries meaning.
function Badge({
  className,
  variant,
  children,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { children: string }) {
  return (
    <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

export { Badge, badgeVariants };

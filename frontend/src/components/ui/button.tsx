import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";
import { Loader2Icon } from "lucide-react";
import { Slot } from "radix-ui";
import type * as React from "react";

const buttonVariants = cva(
  "relative inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-transparent font-medium whitespace-nowrap transition-colors select-none disabled:pointer-events-none disabled:not-aria-busy:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // The one main action of a screen.
        primary: "bg-primary text-primary-foreground shadow-xs hover:bg-primary-hover",
        secondary: "border-input bg-secondary text-secondary-foreground shadow-xs hover:bg-muted",
        subtle: "text-foreground hover:bg-muted",
        danger: "bg-destructive text-destructive-foreground shadow-xs hover:bg-destructive-hover",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        icon: "size-10",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    /** Shows a spinner, keeps the width, and blocks clicks until the work is done. */
    loading?: boolean;
    /** Renders the child (e.g. a router Link) with button styles. Cannot show loading. */
    asChild?: boolean;
  };

function Button({
  className,
  variant,
  size,
  loading = false,
  asChild = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const classes = cn(buttonVariants({ variant, size }), className);

  if (asChild) {
    return (
      <Slot.Root data-slot="button" className={classes} {...props}>
        {children}
      </Slot.Root>
    );
  }

  return (
    <button
      data-slot="button"
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Loader2Icon aria-hidden="true" className="absolute animate-spin" />}
      <span className={cn("inline-flex items-center gap-2", loading && "opacity-0")}>
        {children}
      </span>
    </button>
  );
}

export { Button, buttonVariants };

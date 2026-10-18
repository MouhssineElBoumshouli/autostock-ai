import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";
import { Loader2Icon } from "lucide-react";
import { Slot } from "radix-ui";
import type * as React from "react";

// Material 3 buttons: pill-shaped, with a state layer for hover and press.
const buttonVariants = cva(
  "state-layer inline-flex shrink-0 items-center justify-center gap-2 rounded-full text-label-large whitespace-nowrap transition-[box-shadow,background-color] select-none disabled:pointer-events-none disabled:not-aria-busy:opacity-38 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[18px]",
  {
    variants: {
      variant: {
        // The one main action of a screen.
        filled: "bg-primary text-on-primary hover:shadow-elevation-1",
        // A strong action that is not the main one.
        tonal: "bg-secondary-container text-on-secondary-container hover:shadow-elevation-1",
        outlined: "border border-outline text-primary",
        text: "text-primary",
        // Deleting or turning something off.
        danger: "bg-error text-on-error hover:shadow-elevation-1",
      },
      size: {
        sm: "h-8 px-4",
        md: "h-10 px-6",
        icon: "size-10",
        "icon-sm": "size-8",
      },
    },
    compoundVariants: [
      { variant: "text", size: ["sm", "md"], class: "px-3" },
      { variant: ["text", "outlined"], size: ["icon", "icon-sm"], class: "border-0 text-on-surface-variant" },
    ],
    defaultVariants: { variant: "outlined", size: "md" },
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
      <span className={cn("inline-flex items-center gap-2", loading && "opacity-0")}>{children}</span>
    </button>
  );
}

export { Button, buttonVariants };

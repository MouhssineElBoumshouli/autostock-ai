import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";
import { CheckIcon, ChevronDownIcon } from "lucide-react";
import { Select as SelectPrimitive } from "radix-ui";
import type * as React from "react";

import { fieldClasses } from "@/components/ui/input";

const Select = SelectPrimitive.Root;
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

const triggerVariants = cva("flex items-center justify-between gap-2 text-start [&>span]:truncate", {
  variants: {
    variant: {
      // Inside a form: looks like an outlined text field.
      field: cn(fieldClasses, "data-placeholder:text-on-surface-variant"),
      // A filter chip: 32px tall, 8px corners. Filled once a filter is chosen (data-chosen).
      chip: "state-layer h-8 w-auto rounded-sm border border-outline px-3 text-label-large text-on-surface-variant data-chosen:border-transparent data-chosen:bg-secondary-container data-chosen:text-on-secondary-container",
    },
  },
  defaultVariants: { variant: "field" },
});

function SelectTrigger({
  className,
  children,
  variant,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & VariantProps<typeof triggerVariants>) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(triggerVariants({ variant }), className)}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDownIcon aria-hidden="true" className="size-[18px] shrink-0" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

// Material 3 menu: 4px corners, level 2 shadow.
function SelectContent({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        data-slot="select-content"
        position="popper"
        sideOffset={4}
        className={cn(
          "relative z-50 max-h-(--radix-select-content-available-height) min-w-(--radix-select-trigger-width) overflow-y-auto rounded-xs bg-surface-container py-2 text-on-surface shadow-elevation-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport>{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

function SelectItem({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "relative flex h-12 w-full cursor-default items-center ps-3 pe-10 text-body-large outline-hidden select-none data-disabled:pointer-events-none data-disabled:opacity-38 data-highlighted:bg-on-surface/10 data-[state=checked]:bg-secondary-container/60",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <span className="absolute end-3 flex size-5 items-center justify-center text-on-secondary-container">
        <SelectPrimitive.ItemIndicator>
          <CheckIcon aria-hidden="true" className="size-5" />
        </SelectPrimitive.ItemIndicator>
      </span>
    </SelectPrimitive.Item>
  );
}

export { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue };

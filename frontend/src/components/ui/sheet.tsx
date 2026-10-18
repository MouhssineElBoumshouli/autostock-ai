import { cn } from "cn";
import { Dialog as SheetPrimitive } from "radix-ui";
import type * as React from "react";

// A panel that slides in from the start side (left, or right in Arabic). Tapping outside closes it.
const Sheet = SheetPrimitive.Root;
const SheetTitle = SheetPrimitive.Title;

function SheetContent({ className, children, ...props }: React.ComponentProps<typeof SheetPrimitive.Content>) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-overlay data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        aria-describedby={undefined}
        className={cn(
          "fixed inset-y-0 start-0 z-50 flex w-72 max-w-[85vw] flex-col bg-card shadow-lg outline-none data-open:animate-in data-open:slide-in-from-start data-closed:animate-out data-closed:slide-out-to-start",
          className,
        )}
        {...props}
      >
        {children}
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}

export { Sheet, SheetContent, SheetTitle };

import { cn } from "cn";
import { Dialog as SheetPrimitive } from "radix-ui";
import type * as React from "react";

// A panel that slides in from the start side (left, or right in Arabic) or the end side.
// Tapping outside or pressing Esc closes it.
const Sheet = SheetPrimitive.Root;
const SheetTitle = SheetPrimitive.Title;
const SheetClose = SheetPrimitive.Close;

const sides = {
  start: "start-0 data-open:slide-in-from-start data-closed:slide-out-to-start",
  end: "end-0 data-open:slide-in-from-end data-closed:slide-out-to-end",
};

function SheetContent({
  className,
  children,
  side = "start",
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & { side?: keyof typeof sides }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-overlay data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        aria-describedby={undefined}
        className={cn(
          "fixed inset-y-0 z-50 flex w-72 max-w-[85vw] flex-col bg-card shadow-lg outline-none data-open:animate-in data-closed:animate-out",
          sides[side],
          className,
        )}
        {...props}
      >
        {children}
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}

export { Sheet, SheetClose, SheetContent, SheetTitle };

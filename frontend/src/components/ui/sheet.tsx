import { cn } from "cn";
import { Dialog as SheetPrimitive } from "radix-ui";
import type * as React from "react";

// Material 3 modal side sheet / modal navigation drawer, sliding in from the start side
// (left, or right in Arabic) or the end side. Tapping outside or pressing Esc closes it.
const Sheet = SheetPrimitive.Root;
const SheetTitle = SheetPrimitive.Title;
const SheetClose = SheetPrimitive.Close;

const sides = {
  start: "start-0 rounded-e-lg data-open:slide-in-from-start data-closed:slide-out-to-start",
  end: "end-0 rounded-s-lg data-open:slide-in-from-end data-closed:slide-out-to-end",
};

function SheetContent({
  className,
  children,
  side = "start",
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & { side?: keyof typeof sides }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-scrim/32 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        aria-describedby={undefined}
        className={cn(
          "fixed inset-y-0 z-50 flex w-90 max-w-[85vw] flex-col bg-surface-container-low text-on-surface shadow-elevation-1 outline-none [--field-bg:var(--color-surface-container-low)] data-open:animate-in data-open:duration-300 data-open:ease-emphasized-decelerate data-closed:animate-out data-closed:duration-200",
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

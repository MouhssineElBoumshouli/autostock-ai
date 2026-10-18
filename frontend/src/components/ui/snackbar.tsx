import { Toaster } from "sonner";

// Material 3 snackbar: a short message at the bottom, on the dark inverse surface, that goes away
// by itself. Show one with: toast.success("Order saved") or toast.error("…") — import { toast } from "sonner".
function Snackbar() {
  return (
    <Toaster
      position="bottom-center"
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "flex w-[min(calc(100vw-2rem),36rem)] min-h-12 items-center gap-3 rounded-xs bg-inverse-surface px-4 py-3.5 font-sans text-body-medium text-inverse-on-surface shadow-elevation-3",
          title: "font-normal",
          description: "text-inverse-on-surface/80",
          icon: "hidden",
        },
      }}
    />
  );
}

export { Snackbar };

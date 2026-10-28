import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { forgetAskHistory } from "@/api/ask";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { t } from "@/i18n";

// Forgets the person's saved questions, after asking first (it can't be undone).
export function ClearHistoryButton({ onCleared, disabled }: { onCleared: () => void; disabled?: boolean }) {
  const clear = useMutation({
    mutationFn: forgetAskHistory,
    onSuccess: () => {
      onCleared();
      toast.success(t.ask.assistant.historyCleared);
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="text" size="sm" disabled={disabled} loading={clear.isPending}>
          {t.ask.assistant.clearHistory}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.ask.assistant.clearHistoryTitle}</DialogTitle>
          <DialogDescription>{t.ask.assistant.clearHistoryText}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="text">{t.common.cancel}</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button variant="danger" onClick={() => clear.mutate()}>
              {t.ask.assistant.clearHistory}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

import { toast } from "sonner";

import { type User, useChangeUser } from "@/api/users";
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

// Deactivate asks first (the person is logged out at once). Reactivate happens right away.
export function AccessButton({ user }: { user: User }) {
  const changeUser = useChangeUser();

  function setActive(isActive: boolean) {
    changeUser.mutate(
      { id: user.id, is_active: isActive },
      {
        onSuccess: () => toast.success(isActive ? t.team.reactivated(user.name) : t.team.nowDeactivated(user.name)),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  if (!user.is_active) {
    return (
      <Button size="sm" loading={changeUser.isPending} onClick={() => setActive(true)}>
        {t.team.reactivate}
      </Button>
    );
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="text" disabled={changeUser.isPending}>
          {t.team.deactivate}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.team.deactivateTitle(user.name)}</DialogTitle>
          <DialogDescription>{t.team.deactivateText}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="text">{t.common.cancel}</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button variant="danger" onClick={() => setActive(false)}>
              {t.team.deactivate}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

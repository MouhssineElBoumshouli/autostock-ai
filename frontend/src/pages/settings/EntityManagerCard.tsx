import type { UseMutationResult } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/ErrorState";
import { FormError } from "@/components/FormError";
import { FormField } from "@/components/FormField";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { requiredError } from "@/lib/validation";

export type ManagedEntity = { id: string; name: string; in_use: boolean };

// Branches and suppliers are managed the same way: rename, merge one into another
// (moving its stock/sales or parts along), or remove one that was never used.
export function EntityManagerCard({
  title,
  description,
  usedNote,
  items,
  isPending,
  isError,
  onRetry,
  retrying,
  rename,
  merge,
  remove,
}: {
  title: string;
  description: string;
  usedNote: string;
  items: ManagedEntity[] | undefined;
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
  retrying: boolean;
  rename: UseMutationResult<ManagedEntity, Error, { id: string; name: string }>;
  merge: UseMutationResult<void, Error, { id: string; into: string }>;
  remove: UseMutationResult<void, Error, string>;
}) {
  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-1 px-0">
        {isError ? (
          <div className="px-6">
            <ErrorState onRetry={onRetry} retrying={retrying} />
          </div>
        ) : isPending ? (
          <div className="grid gap-3 px-6" aria-busy="true">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : (
          <>
            <p className="px-6 pb-2 text-body-medium text-on-surface-variant">{description}</p>
            <ul className="divide-y border-t">
              {items!.map((item) => (
                <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-6 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-body-large">{item.name}</span>
                    {item.in_use && <Badge variant="neutral">{usedNote}</Badge>}
                  </div>
                  <div className="flex gap-1">
                    <RenameButton item={item} rename={rename} />
                    {items!.length > 1 && <MergeButton item={item} items={items!} merge={merge} />}
                    <RemoveButton item={item} remove={remove} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function RenameButton({
  item,
  rename,
}: {
  item: ManagedEntity;
  rename: UseMutationResult<ManagedEntity, Error, { id: string; name: string }>;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(item.name);
  const [showError, setShowError] = useState(false);

  function changeOpen(next: boolean) {
    if (next) setName(item.name);
    setShowError(false);
    rename.reset();
    setOpen(next);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setShowError(true);
    if (requiredError(name)) return;
    rename.mutate(
      { id: item.id, name: name.trim() },
      { onSuccess: () => { toast.success(t.settings.entities.renamed(item.name, name.trim())); changeOpen(false); } },
    );
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="text">
          {t.settings.entities.rename}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.settings.entities.renameTitle(item.name)}</DialogTitle>
        </DialogHeader>
        <form noValidate onSubmit={submit} className="grid gap-5">
          <FormField label={t.settings.entities.nameField} error={showError ? requiredError(name) : undefined}>
            {(field) => <Input {...field} value={name} onChange={(e) => setName(e.target.value)} />}
          </FormField>
          <FormError message={rename.error?.message} />
          <DialogFooter>
            <Button type="button" variant="text" onClick={() => changeOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" variant="filled" loading={rename.isPending}>
              {t.common.save}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function MergeButton({
  item,
  items,
  merge,
}: {
  item: ManagedEntity;
  items: ManagedEntity[];
  merge: UseMutationResult<void, Error, { id: string; into: string }>;
}) {
  const others = items.filter((other) => other.id !== item.id);
  const [open, setOpen] = useState(false);
  const [into, setInto] = useState(others[0]?.id ?? "");

  function changeOpen(next: boolean) {
    if (next) setInto(others[0]?.id ?? "");
    merge.reset();
    setOpen(next);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const target = items.find((other) => other.id === into);
    if (!target) return;
    merge.mutate(
      { id: item.id, into },
      { onSuccess: () => { toast.success(t.settings.entities.merged(item.name, target.name)); changeOpen(false); } },
    );
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="text">
          {t.settings.entities.merge}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.settings.entities.mergeTitle(item.name)}</DialogTitle>
          <DialogDescription>{t.settings.entities.mergeText(item.name)}</DialogDescription>
        </DialogHeader>
        <form noValidate onSubmit={submit} className="grid gap-5">
          <FormField label={t.settings.entities.mergeInto}>
            {(field) => (
              <Select value={into} onValueChange={setInto}>
                <SelectTrigger {...field}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {others.map((other) => (
                    <SelectItem key={other.id} value={other.id}>
                      {other.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormError message={merge.error?.message} />
          <DialogFooter>
            <Button type="button" variant="text" onClick={() => changeOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button type="submit" variant="filled" loading={merge.isPending}>
              {t.settings.entities.merge}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RemoveButton({ item, remove }: { item: ManagedEntity; remove: UseMutationResult<void, Error, string> }) {
  function confirmed() {
    remove.mutate(item.id, {
      onSuccess: () => toast.success(t.settings.entities.removed(item.name)),
      onError: (error) => toast.error(error.message),
    });
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="text" disabled={remove.isPending}>
          {t.common.remove}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.settings.entities.removeTitle(item.name)}</DialogTitle>
          <DialogDescription>
            {item.in_use ? t.settings.entities.removeBlockedText : t.settings.entities.removeText}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="text">{t.common.cancel}</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button variant="danger" onClick={confirmed} disabled={item.in_use}>
              {t.common.remove}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

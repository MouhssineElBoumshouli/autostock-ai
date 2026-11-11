import { useBranches, useMergeBranch, useRemoveBranch, useRenameBranch } from "@/api/branches";
import { t } from "@/i18n";

import { EntityManagerCard } from "./EntityManagerCard";

export function BranchesCard() {
  const branches = useBranches();
  const rename = useRenameBranch();
  const merge = useMergeBranch();
  const remove = useRemoveBranch();

  return (
    <EntityManagerCard
      title={t.settings.branches.title}
      description={t.settings.branches.description}
      usedNote={t.settings.branches.usedNote}
      items={branches.data}
      isPending={branches.isPending}
      isError={branches.isError}
      onRetry={() => branches.refetch()}
      retrying={branches.isFetching}
      rename={rename}
      merge={merge}
      remove={remove}
      rowNote={(branch) =>
        !branch.in_use && <p className="w-full text-body-medium text-on-surface-variant">{t.settings.branches.emptyNote}</p>
      }
    />
  );
}

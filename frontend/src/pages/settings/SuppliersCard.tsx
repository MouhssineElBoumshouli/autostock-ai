import { useMergeSupplier, useRemoveSupplier, useRenameSupplier, useSuppliers } from "@/api/suppliers";
import { t } from "@/i18n";

import { EntityManagerCard } from "./EntityManagerCard";

export function SuppliersCard() {
  const suppliers = useSuppliers();
  const rename = useRenameSupplier();
  const merge = useMergeSupplier();
  const remove = useRemoveSupplier();

  return (
    <EntityManagerCard
      title={t.settings.suppliers.title}
      description={t.settings.suppliers.description}
      usedNote={t.settings.suppliers.usedNote}
      items={suppliers.data}
      isPending={suppliers.isPending}
      isError={suppliers.isError}
      onRetry={() => suppliers.refetch()}
      retrying={suppliers.isFetching}
      rename={rename}
      merge={merge}
      remove={remove}
    />
  );
}

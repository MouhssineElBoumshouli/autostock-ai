import {
  useAddSupplier,
  useMergeSupplier,
  useRemoveSupplier,
  useRenameSupplier,
  useSaveSupplierDetails,
  useSuppliers,
} from "@/api/suppliers";
import { t } from "@/i18n";

import { EntityManagerCard } from "./EntityManagerCard";
import { AddSupplierDialog, DeliveryTimeButton } from "./SupplierDialogs";

export function SuppliersCard() {
  const suppliers = useSuppliers();
  const add = useAddSupplier();
  const rename = useRenameSupplier();
  const saveDetails = useSaveSupplierDetails();
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
      headerAction={<AddSupplierDialog add={add} />}
      rowExtra={(supplier) => <DeliveryTimeButton supplier={supplier} save={saveDetails} />}
    />
  );
}

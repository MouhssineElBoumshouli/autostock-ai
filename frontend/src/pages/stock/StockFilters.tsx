import { useEffect, useState } from "react";

import { type StatusFilter, statusFilters, useStockFilterChoices } from "@/api/stock";
import { FilterChip } from "@/components/FilterChip";
import { SearchInput } from "@/components/SearchInput";
import { t } from "@/i18n";

export type StockFilterValues = {
  search: string;
  status?: StatusFilter;
  category?: string;
  branch?: string;
  supplier?: string;
};

const statusLabels: Record<StatusFilter, string> = {
  healthy: t.stock.healthy,
  low: t.stock.low,
  out: t.stock.out,
  dead: t.stock.filters.dead,
  inactive: t.stock.inactive,
};

// A search bar and four filter chips. Typing waits a moment before searching, so each key press doesn't reload.
export function StockFilters({
  values,
  onChange,
}: {
  values: StockFilterValues;
  onChange: (changes: Partial<Record<keyof StockFilterValues, string | undefined>>) => void;
}) {
  const choices = useStockFilterChoices().data;
  const [search, setSearch] = useState(values.search);

  useEffect(() => setSearch(values.search), [values.search]);
  useEffect(() => {
    if (search === values.search) return;
    const timer = setTimeout(() => onChange({ search }), 300);
    return () => clearTimeout(timer);
  }, [search, values.search, onChange]);

  return (
    <div className="grid gap-3">
      <div className="max-w-xl">
        <SearchInput
          label={t.stock.searchLabel}
          placeholder={t.stock.searchPlaceholder}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <FilterChip
          label={t.stock.filters.status}
          value={values.status}
          allLabel={t.stock.filters.allStatuses}
          options={statusFilters.map((status) => ({ value: status, label: statusLabels[status] }))}
          onChange={(status) => onChange({ status })}
        />
        <FilterChip
          label={t.stock.filters.category}
          value={values.category}
          allLabel={t.stock.filters.allCategories}
          options={(choices?.categories ?? []).map((category) => ({ value: category, label: category }))}
          onChange={(category) => onChange({ category })}
        />
        <FilterChip
          label={t.stock.filters.branch}
          value={values.branch}
          allLabel={t.stock.filters.allBranches}
          options={(choices?.branches ?? []).map((branch) => ({ value: branch.id, label: branch.name }))}
          onChange={(branch) => onChange({ branch })}
        />
        <FilterChip
          label={t.stock.filters.supplier}
          value={values.supplier}
          allLabel={t.stock.filters.allSuppliers}
          options={(choices?.suppliers ?? []).map((supplier) => ({ value: supplier.id, label: supplier.name }))}
          onChange={(supplier) => onChange({ supplier })}
        />
      </div>
    </div>
  );
}

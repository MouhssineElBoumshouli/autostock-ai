import { useEffect, useState } from "react";

import { type StatusFilter, statusFilters, useStockFilterChoices } from "@/api/stock";
import { SearchInput } from "@/components/SearchInput";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { t } from "@/i18n";

export const ALL = "all";

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

// Search plus four filters. Typing waits a moment before searching, so each key press doesn't reload.
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
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(16rem,2fr)_repeat(4,minmax(0,1fr))]">
      <div className="md:col-span-2 xl:col-span-1">
        <SearchInput
          label={t.stock.searchLabel}
          placeholder={t.stock.searchPlaceholder}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <FilterSelect
        label={t.stock.filters.status}
        value={values.status}
        allLabel={t.stock.filters.allStatuses}
        options={statusFilters.map((status) => ({ value: status, label: statusLabels[status] }))}
        onChange={(status) => onChange({ status })}
      />
      <FilterSelect
        label={t.stock.filters.category}
        value={values.category}
        allLabel={t.stock.filters.allCategories}
        options={(choices?.categories ?? []).map((category) => ({ value: category, label: category }))}
        onChange={(category) => onChange({ category })}
      />
      <FilterSelect
        label={t.stock.filters.branch}
        value={values.branch}
        allLabel={t.stock.filters.allBranches}
        options={(choices?.branches ?? []).map((branch) => ({ value: branch.id, label: branch.name }))}
        onChange={(branch) => onChange({ branch })}
      />
      <FilterSelect
        label={t.stock.filters.supplier}
        value={values.supplier}
        allLabel={t.stock.filters.allSuppliers}
        options={(choices?.suppliers ?? []).map((supplier) => ({ value: supplier.id, label: supplier.name }))}
        onChange={(supplier) => onChange({ supplier })}
      />
    </div>
  );
}

// A compact filter without a visible label: screen readers hear `label`, and "All …" says what it filters.
function FilterSelect({
  label,
  value,
  allLabel,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  allLabel: string;
  options: { value: string; label: string }[];
  onChange: (value: string | undefined) => void;
}) {
  return (
    <div>
      <Select value={value ?? ALL} onValueChange={(next) => onChange(next === ALL ? undefined : next)}>
        <SelectTrigger aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{allLabel}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

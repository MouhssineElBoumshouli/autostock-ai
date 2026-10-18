import { FilterIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { type StatusFilter, statusFilters, useStockFilterChoices } from "@/api/stock";
import { FilterChip } from "@/components/FilterChip";
import { SearchInput } from "@/components/SearchInput";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
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

// A search bar, then four filter chips on tablet and up. On a phone they go behind a
// "Filters" button instead, so the search bar and the parts list below it aren't pushed down.
// Typing waits a moment before searching, so each key press doesn't reload.
export function StockFilters({
  values,
  onChange,
}: {
  values: StockFilterValues;
  onChange: (changes: Partial<Record<keyof StockFilterValues, string | undefined>>) => void;
}) {
  const choices = useStockFilterChoices().data;
  const [search, setSearch] = useState(values.search);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => setSearch(values.search), [values.search]);
  useEffect(() => {
    if (search === values.search) return;
    const timer = setTimeout(() => onChange({ search }), 300);
    return () => clearTimeout(timer);
  }, [search, values.search, onChange]);

  const activeCount = [values.status, values.category, values.branch, values.supplier].filter(Boolean).length;

  const chips = (
    <>
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
    </>
  );

  return (
    <div className="grid gap-3">
      <div className="flex max-w-xl gap-2">
        <div className="min-w-0 flex-1">
          <SearchInput
            label={t.stock.searchLabel}
            placeholder={t.stock.searchPlaceholder}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <Button variant="outlined" className="shrink-0 sm:hidden" onClick={() => setSheetOpen(true)}>
          <FilterIcon aria-hidden="true" />
          {activeCount > 0 ? t.stock.filters.openFiltersWithCount(activeCount) : t.stock.filters.openFilters}
        </Button>
      </div>
      <div className="hidden flex-wrap gap-2 sm:flex">{chips}</div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="end" className="gap-0">
          <div className="flex items-center justify-between border-b p-4">
            <SheetTitle className="text-title-large">{t.stock.filters.title}</SheetTitle>
            {activeCount > 0 && (
              <Button variant="text" size="sm" onClick={() => onChange({ status: undefined, category: undefined, branch: undefined, supplier: undefined })}>
                {t.common.clearFilters}
              </Button>
            )}
          </div>
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-4">{chips}</div>
          <div className="border-t p-4">
            <Button variant="filled" className="w-full" onClick={() => setSheetOpen(false)}>
              {t.stock.filters.done}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

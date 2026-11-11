import type { AskFilters } from "@/api/ask";
import type { Choice } from "@/api/stock";
import { FilterChip } from "@/components/FilterChip";
import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

import { ASK_FILTERS, ASK_PERIODS, typeLabel } from "./questionTypes";

// "I understood: ..." as small chips. The question type and the part are shown but fixed; a
// category, branch or period this question type takes can be changed from a short list, which
// re-asks the same question with that one filter changed, without retyping.
export function UnderstoodChips({
  questionType,
  filters,
  categories,
  branches,
  onChange,
}: {
  questionType: string;
  filters: AskFilters;
  categories: string[];
  branches: Choice[];
  onChange: (filters: AskFilters) => void;
}) {
  const allowed = ASK_FILTERS[questionType] ?? [];

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="neutral">{typeLabel(questionType)}</Badge>
      {filters.part && <Badge variant="neutral">{t.ask.partChip(filters.part)}</Badge>}
      {allowed.includes("category") && (
        <FilterChip
          label={t.ask.filters.category}
          value={filters.category}
          allLabel={t.ask.filters.allCategories}
          options={categories.map((category) => ({ value: category, label: category }))}
          onChange={(category) => onChange({ ...filters, category })}
        />
      )}
      {allowed.includes("branch") && (
        <FilterChip
          label={t.ask.filters.branch}
          value={filters.branch}
          allLabel={t.ask.filters.allBranches}
          options={branches.map((branch) => ({ value: branch.name, label: branch.name }))}
          onChange={(branch) => onChange({ ...filters, branch })}
        />
      )}
      {allowed.includes("period") && (
        <FilterChip
          label={t.ask.filters.period}
          value={filters.period}
          allLabel={t.ask.filters.allPeriods}
          options={ASK_PERIODS.map((period) => ({ value: period, label: t.ask.periods[period] }))}
          onChange={(period) => onChange({ ...filters, period })}
        />
      )}
    </div>
  );
}

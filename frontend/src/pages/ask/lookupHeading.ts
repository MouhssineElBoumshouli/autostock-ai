import type { LookupFilters } from "@/api/ask";
import { t } from "@/i18n";
import { formatDayRange, isolate } from "@/lib/format";

import { understoodHeading } from "./askSentence";

// The heading above one lookup's numbers: "Sales · Filtre à huile · Dacia Logan · Rabat - Agdal · 1 Oct – 31 Oct · by week".
// The online assistant's tools have their own words (t.ask.toolHeadings); the app's own lookups use the
// question type's heading.
export function lookupHeading(tool: string, filters: LookupFilters): string {
  const title = t.ask.toolHeadings[tool];
  if (!title) return understoodHeading(tool, filters, filters.period ?? null);
  const words = t.ask.lookupWords;
  const pieces = [title];
  for (const name of ["type", "car", "brand", "oem", "category", "branch", "supplier"]) {
    if (filters[name]) pieces.push(isolate(filters[name]));
  }
  if (filters.range) pieces.push(formatDayRange(filters.range));
  if (filters.days) pieces.push(words.nextDays(filters.days));
  if (filters.group_by && words.groupBy[filters.group_by]) pieces.push(words.groupBy[filters.group_by]);
  if (filters.compare && words.compare[filters.compare]) pieces.push(words.compare[filters.compare]);
  if (filters.only && words.only[filters.only]) pieces.push(words.only[filters.only]);
  if (filters.status && words.status[filters.status]) pieces.push(words.status[filters.status]);
  if (filters.show && words.show[filters.show]) pieces.push(words.show[filters.show]);
  return pieces.join(" · ");
}

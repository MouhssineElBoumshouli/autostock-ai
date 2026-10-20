import type { ActivityItem } from "@/api/activity";
import type { CareLevel } from "@/api/orders";
import type { Role } from "@/api/users";
import { t } from "@/i18n";
import { formatNumber } from "@/lib/format";

const words = t.activity.sentences;

function roleName(role: unknown): string {
  return t.roles[role as Role] ?? String(role);
}

function careLevelName(level: unknown): string {
  return t.orders.settings.levels[level as CareLevel] ?? String(level);
}

// Turns one audit log row into a plain sentence, e.g. "Sara changed Youssef's role from Staff to Manager."
export function activitySentence(item: ActivityItem): string {
  const actor = item.actor?.name ?? t.activity.someone;
  const target = item.target?.name ?? t.activity.someone;
  const self = item.actor !== null && item.actor.id === item.target?.id;
  const before = item.before ?? {};
  const after = item.after ?? {};

  switch (item.action) {
    case "organization.created":
      return words.shopCreated(actor, String(after.name ?? t.activity.shop));
    case "organization.updated":
      return [
        before.name !== after.name && words.shopRenamed(actor, String(before.name), String(after.name)),
        before.currency !== after.currency && words.currencyChanged(actor, String(before.currency), String(after.currency)),
        before.order_service_target !== undefined &&
          after.order_service_target !== undefined &&
          before.order_service_target !== after.order_service_target &&
          words.orderCareChanged(actor, careLevelName(after.order_service_target)),
      ]
        .filter(Boolean)
        .join(" ");
    case "synonyms.updated":
      return words.synonymsChanged(actor);
    case "user.created":
      return self
        ? words.joinedAsFounder(actor, roleName(after.role))
        : words.personAdded(actor, target, roleName(after.role));
    case "user.updated":
      return [
        before.role !== after.role &&
          (self
            ? words.ownRoleChanged(actor, roleName(before.role), roleName(after.role))
            : words.roleChanged(actor, target, roleName(before.role), roleName(after.role))),
        before.is_active !== after.is_active &&
          (after.is_active
            ? words.reactivated(actor, target)
            : self
              ? words.deactivatedSelf(actor)
              : words.deactivated(actor, target)),
      ]
        .filter(Boolean)
        .join(" ");
    case "user.password_changed":
      return words.passwordChanged(actor);
    case "user.password_reset":
      return words.passwordReset(actor, target);
    case "import.saved":
      return after.kind === "sales"
        ? words.importedSales(actor, String(after.file_name), formatNumber(Number(after.new_sales ?? 0)))
        : after.kind === "equivalents"
          ? words.importedEquivalents(actor, String(after.file_name), formatNumber(Number(after.new_equivalents ?? 0)))
          : words.importedParts(
              actor,
              String(after.file_name),
              formatNumber(Number(after.new_parts ?? 0)),
              formatNumber(Number(after.updated_parts ?? 0)),
            );
    case "part.updated":
      return words.partEdited(actor, String(after.name), String(after.sku));
    case "part_equivalent.linked":
      return words.partsLinked(actor, String(after.part), String(after.other_part));
    case "part_equivalent.removed":
      return words.partsUnlinked(actor, String(before.part), String(before.other_part));
    case "user.logged_in":
      return words.loggedIn(actor);
    case "branch.renamed":
      return words.branchRenamed(actor, String(before.name), String(after.name));
    case "branch.merged":
      return words.branchMerged(actor, String(after.from), String(after.into));
    case "branch.removed":
      return words.branchRemoved(actor, String(before.name));
    case "supplier.merged":
      return words.supplierMerged(actor, String(after.from), String(after.into));
    case "supplier.removed":
      return words.supplierRemoved(actor, String(before.name));
    case "forecast.requested":
      return words.forecastRequested(actor);
    case "order_suggestions.created":
      return "cut" in after
        ? words.suggestionsCreated(actor, formatNumber(Number(after.lines ?? 0)), formatNumber(Number(after.cut ?? 0)))
        : words.suggestionsCreatedEmpty(actor);
    case "order_suggestion.approved":
      return words.orderApproved(actor, formatNumber(Number(after.quantity ?? 0)), String(after.part), String(after.branch));
    case "order_suggestion.rejected":
      return words.orderRejected(actor, String(after.part), String(after.branch));
    case "purchase_order.created":
      return words.purchaseOrderCreated(actor, String(after.order_number), String(after.supplier));
    case "purchase_order.sent":
      return words.purchaseOrderSent(actor, String(after.order_number), String(after.supplier));
    case "purchase_order.received":
      return words.purchaseOrderReceived(actor, String(after.order_number), String(after.supplier));
    case "stock_level.received":
      return words.stockReceived(
        actor,
        formatNumber(Number(after.quantity) - Number(before.quantity)),
        String(after.part),
        String(after.branch),
        String(after.order_number),
      );
    default:
      return words.otherChange(actor);
  }
}

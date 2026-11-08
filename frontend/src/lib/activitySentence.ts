import type { ActivityItem } from "@/api/activity";
import type { CareLevel } from "@/api/orders";
import type { Role } from "@/api/users";
import { isLanguage, languageNames, t } from "@/i18n";
import { deliveriesText } from "@/lib/deliveryTime";
import { formatNumber, isolate } from "@/lib/format";

const words = t.activity.sentences;

function roleName(role: unknown): string {
  return t.roles[role as Role] ?? String(role);
}

function careLevelName(level: unknown): string {
  return t.orders.settings.levels[level as CareLevel] ?? String(level);
}

// A supplier's delivery time changed: typed by the owner, back to automatic, from a file, or learned.
function deliveryTimeSentence(actor: string, name: string, after: Record<string, unknown>): string {
  if (after.delivery_days === null || after.delivery_days === undefined) return words.deliveryTimeAutomatic(actor, name);
  const count = Number(after.delivery_days);
  const days = t.common.days(count, formatNumber(count));
  if (after.source === "learned") return words.deliveryTimeLearned(name, days, deliveriesText(Number(after.learned_from)));
  if (after.source === "file") return words.deliveryTimeFromFile(actor, name, days);
  return words.deliveryTimeSetByOwner(actor, name, days);
}

// Turns one audit log row into a plain sentence, e.g. "Sara changed Youssef's role from Staff to Manager."
export function activitySentence(item: ActivityItem): string {
  const actor = item.actor ? isolate(item.actor.name) : t.activity.someone;
  const target = item.target ? isolate(item.target.name) : t.activity.someone;
  const self = item.actor !== null && item.actor.id === item.target?.id;
  const before = item.before ?? {};
  const after = item.after ?? {};

  switch (item.action) {
    case "organization.created":
      return words.shopCreated(actor, isolate(String(after.name ?? t.activity.shop)));
    case "organization.updated":
      return [
        before.name !== after.name && words.shopRenamed(actor, isolate(String(before.name)), isolate(String(after.name))),
        before.currency !== after.currency && words.currencyChanged(actor, String(before.currency), String(after.currency)),
        before.order_service_target !== undefined &&
          after.order_service_target !== undefined &&
          before.order_service_target !== after.order_service_target &&
          words.orderCareChanged(actor, careLevelName(after.order_service_target)),
        before.language !== undefined &&
          before.language !== after.language &&
          isLanguage(after.language) &&
          words.languageChanged(actor, languageNames[after.language]),
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
    case "user.password_set_on_shop_computer":
      return words.passwordSetOnShopComputer(actor);
    case "user.password_reset":
      return words.passwordReset(actor, target);
    case "import.saved":
      return after.kind === "sales"
        ? words.importedSales(actor, isolate(String(after.file_name)), formatNumber(Number(after.new_sales ?? 0)))
        : after.kind === "equivalents"
          ? words.importedEquivalents(actor, isolate(String(after.file_name)), formatNumber(Number(after.new_equivalents ?? 0)))
          : words.importedParts(
              actor,
              isolate(String(after.file_name)),
              formatNumber(Number(after.new_parts ?? 0)),
              formatNumber(Number(after.updated_parts ?? 0)),
            );
    case "part.updated":
      return words.partEdited(actor, isolate(String(after.name)), isolate(String(after.sku)));
    case "part_equivalent.linked":
      return words.partsLinked(actor, isolate(String(after.part)), isolate(String(after.other_part)));
    case "part_equivalent.removed":
      return words.partsUnlinked(actor, isolate(String(before.part)), isolate(String(before.other_part)));
    case "user.logged_in":
      return words.loggedIn(actor);
    case "branch.renamed":
      return words.branchRenamed(actor, isolate(String(before.name)), isolate(String(after.name)));
    case "branch.merged":
      return words.branchMerged(actor, isolate(String(after.from)), isolate(String(after.into)));
    case "branch.removed":
      return words.branchRemoved(actor, isolate(String(before.name)));
    case "supplier.added":
      return words.supplierAdded(actor, isolate(String(after.name)));
    case "supplier.details_updated":
      return words.supplierDetailsUpdated(actor, isolate(String(after.name)));
    case "supplier.delivery_time_changed":
      return deliveryTimeSentence(actor, isolate(String(after.name)), after);
    case "supplier.merged":
      return words.supplierMerged(actor, isolate(String(after.from)), isolate(String(after.into)));
    case "supplier.removed":
      return words.supplierRemoved(actor, isolate(String(before.name)));
    case "data.exported":
      return words.dataExported(actor);
    case "start_here.hidden_changed":
      return after.hidden ? words.startHereHidden(actor) : words.startHereShown(actor);
    case "forecast.requested":
      return words.forecastRequested(actor);
    case "order_suggestions.created":
      return "cut" in after
        ? words.suggestionsCreated(actor, formatNumber(Number(after.lines ?? 0)), formatNumber(Number(after.cut ?? 0)))
        : words.suggestionsCreatedEmpty(actor);
    case "order_suggestion.approved":
      return words.orderApproved(actor, formatNumber(Number(after.quantity ?? 0)), isolate(String(after.part)), isolate(String(after.branch)));
    case "order_suggestion.rejected":
      return words.orderRejected(actor, isolate(String(after.part)), isolate(String(after.branch)));
    case "purchase_order.created":
      return words.purchaseOrderCreated(actor, isolate(String(after.order_number)), isolate(String(after.supplier)));
    case "purchase_order.sent":
      return words.purchaseOrderSent(actor, isolate(String(after.order_number)), isolate(String(after.supplier)));
    case "purchase_order.received":
      return words.purchaseOrderReceived(actor, isolate(String(after.order_number)), isolate(String(after.supplier)));
    case "stock_level.received":
      return words.stockReceived(
        actor,
        formatNumber(Number(after.quantity) - Number(before.quantity)),
        isolate(String(after.part)),
        isolate(String(after.branch)),
        isolate(String(after.order_number)),
      );
    case "alert.reviewed":
      return after.status === "not_a_problem"
        ? words.alertNotAProblem(actor, isolate(String(after.part)), isolate(String(after.branch)))
        : words.alertLookedAt(actor, isolate(String(after.part)), isolate(String(after.branch)));
    default:
      return words.otherChange(actor);
  }
}

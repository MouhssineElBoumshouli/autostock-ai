import type { ActivityItem } from "@/api/activity";
import type { Role } from "@/api/users";
import { t } from "@/i18n";

const words = t.activity.sentences;

function roleName(role: unknown): string {
  return t.roles[role as Role] ?? String(role);
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
      ]
        .filter(Boolean)
        .join(" ");
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
    case "user.logged_in":
      return words.loggedIn(actor);
    default:
      return words.otherChange(actor);
  }
}

import { toast } from "sonner";

import { type Role, roles, type User, useChangeUser } from "@/api/users";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { t } from "@/i18n";

export function RoleSelect({ user }: { user: User }) {
  const changeUser = useChangeUser();

  function changeRole(role: string) {
    changeUser.mutate(
      { id: user.id, role: role as Role },
      {
        onSuccess: () => toast.success(t.team.roleChanged(user.name, t.roles[role as Role])),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <Select value={user.role} onValueChange={changeRole} disabled={changeUser.isPending}>
      <SelectTrigger aria-label={t.team.changeRoleLabel(user.name)} className="h-9 w-32">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {roles.map((role) => (
          <SelectItem key={role} value={role}>
            {t.roles[role]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

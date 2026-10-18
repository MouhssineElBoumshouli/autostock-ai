import { UserPlusIcon } from "lucide-react";
import { useState } from "react";

import { useSignedIn } from "@/components/SignedIn";
import { type User, useUsers } from "@/api/users";
import { type Column, DataTable } from "@/components/DataTable";
import { ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { t } from "@/i18n";
import { formatDateTime } from "@/lib/format";

import { AccessButton } from "./AccessButton";
import { AddPersonDialog } from "./AddPersonDialog";
import { ResetPasswordDialog } from "./ResetPasswordDialog";
import { RoleSelect } from "./RoleSelect";

// Owners only: everyone who can use AutoStock in this shop.
export function TeamPage() {
  const users = useUsers();
  const myId = useSignedIn().user.id;
  const [adding, setAdding] = useState(false);

  const columns: Column<User>[] = [
    {
      header: t.team.columns.person,
      primary: true,
      cell: (user) => (
        <div className="grid">
          <span className="font-medium">
            {user.name}
            {user.id === myId && <span className="font-normal text-on-surface-variant"> ({t.common.you})</span>}
          </span>
          <span className="text-body-small text-on-surface-variant">{user.email}</span>
        </div>
      ),
    },
    { header: t.team.columns.role, cell: (user) => <RoleSelect user={user} /> },
    {
      header: t.team.columns.status,
      cell: (user) =>
        !user.is_active ? (
          <Badge variant="neutral">{t.team.deactivated}</Badge>
        ) : user.must_change_password ? (
          <Badge variant="warning">{t.team.needsNewPassword}</Badge>
        ) : (
          <Badge variant="success">{t.team.active}</Badge>
        ),
    },
    {
      header: t.team.columns.lastLogin,
      cell: (user) => (user.last_login_at ? formatDateTime(user.last_login_at) : t.common.never),
    },
    {
      header: t.team.columns.access,
      align: "end",
      cell: (user) => (
        <div className="flex justify-end gap-1">
          {user.id !== myId && <ResetPasswordDialog user={user} />}
          <AccessButton user={user} />
        </div>
      ),
    },
  ];

  return (
    <div className="grid gap-8">
      <PageHeader
        title={t.nav.team}
        subtitle={t.team.subtitle}
        action={
          <Button variant="filled" onClick={() => setAdding(true)}>
            <UserPlusIcon aria-hidden="true" />
            {t.team.addPerson}
          </Button>
        }
      />
      <Card className="py-0">
        {users.isError ? (
          <ErrorState onRetry={() => users.refetch()} retrying={users.isFetching} />
        ) : (
          <DataTable columns={columns} rows={users.data ?? []} rowKey={(user) => user.id} loading={users.isPending} />
        )}
      </Card>
      <AddPersonDialog open={adding} onOpenChange={setAdding} />
    </div>
  );
}

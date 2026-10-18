import { ArrowLeftIcon, UserPlusIcon } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useMe } from "@/api/auth";
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
  const myId = useMe().data?.user.id;
  const [adding, setAdding] = useState(false);

  const columns: Column<User>[] = [
    {
      header: t.team.columns.person,
      primary: true,
      cell: (user) => (
        <div className="grid">
          <span className="font-medium">
            {user.name}
            {user.id === myId && <span className="font-normal text-muted-foreground"> ({t.common.you})</span>}
          </span>
          <span className="text-xs text-muted-foreground">{user.email}</span>
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
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
      {/* Until the app layout arrives in Step 1d */}
      <Button variant="subtle" size="sm" asChild className="-ms-3 w-fit">
        <Link to="/">
          <ArrowLeftIcon aria-hidden="true" className="rtl:rotate-180" />
          {t.common.backHome}
        </Link>
      </Button>
      <PageHeader
        title={t.team.title}
        subtitle={t.team.subtitle}
        action={
          <Button variant="primary" onClick={() => setAdding(true)}>
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
    </main>
  );
}

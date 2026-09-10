"use client";

import { AdminsCreateFormSection } from "@/features/admins/components/AdminsCreateFormSection";
import { AdminsResetPasswordDialog } from "@/features/admins/components/AdminsResetPasswordDialog";
import { AdminsTableSection } from "@/features/admins/components/AdminsTableSection";
import { PageHeader } from "@/components/layout/PageHeader";
import type { AdminsPageVm } from "@/features/admins/hooks/use-admins-page";
import { ADMINS_FORBIDDEN_DESCRIPTION, ADMINS_PAGE_DESCRIPTION } from "@/features/admins/lib/admins-page-shared";

export function AdminsPageView({ vm }: { vm: AdminsPageVm }) {
  const { forbidden, showForm, setShowForm, msg, err } = vm;

  if (forbidden) {
    return (
      <div className="admin-page-stack">
        <PageHeader title="平台管理员" description={ADMINS_FORBIDDEN_DESCRIPTION} />
        <p className="text-sm text-ink-muted">当前账号无权限查看此页面。</p>
      </div>
    );
  }

  return (
    <>
      <div className="admin-page-stack">
        <PageHeader
          title="平台管理员"
          description={ADMINS_PAGE_DESCRIPTION}
          action={
            <button type="button" className="btn-primary" onClick={() => setShowForm((v) => !v)}>
              {showForm ? "取消" : "新建管理员"}
            </button>
          }
        />

        {msg && <p className="admin-alert-ok">{msg}</p>}
        {err && <p className="admin-alert-err">{err}</p>}

        <AdminsCreateFormSection vm={vm} />
        <AdminsTableSection vm={vm} />
      </div>
      <AdminsResetPasswordDialog vm={vm} />
    </>
  );
}

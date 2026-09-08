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
      <div>
        <PageHeader title="平台管理员" description={ADMINS_FORBIDDEN_DESCRIPTION} />
        <p className="text-sm text-ink-muted">当前账号无权限查看此页面。</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="平台管理员"
        description={ADMINS_PAGE_DESCRIPTION}
        action={
          <button type="button" className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "取消" : "新建管理员"}
          </button>
        }
      />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      <AdminsCreateFormSection vm={vm} />
      <AdminsTableSection vm={vm} />
      <AdminsResetPasswordDialog vm={vm} />
    </div>
  );
}

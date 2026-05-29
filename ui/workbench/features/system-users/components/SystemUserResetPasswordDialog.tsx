"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type { SystemUsersPageVm } from "@/features/system-users/hooks/use-system-users-page";

export function SystemUserResetPasswordDialog({ vm }: { vm: SystemUsersPageVm }) {
  const { resetUser, setResetUser, resetPassword, setResetPassword, onConfirmResetPassword } = vm;

  return (
    <ResourceDialog
      open={!!resetUser}
      title="重置密码"
      onClose={() => setResetUser(null)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setResetUser(null)}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={resetPassword.length < 6} onClick={() => void onConfirmResetPassword()}>
            确认重置
          </button>
        </>
      }
    >
      <p className="text-sm text-ink-muted">
        为用户 <span className="font-medium text-ink">{resetUser?.username}</span> 设置新密码。重置后该用户在所有设备上的登录将失效。
      </p>
      <input
        className="input-field mt-3 w-full"
        placeholder="新密码（至少 6 位）"
        type="password"
        value={resetPassword}
        onChange={(e) => setResetPassword(e.target.value)}
      />
    </ResourceDialog>
  );
}

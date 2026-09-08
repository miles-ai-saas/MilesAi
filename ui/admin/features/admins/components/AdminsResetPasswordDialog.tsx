"use client";

import type { AdminsPageVm } from "@/features/admins/hooks/use-admins-page";

export function AdminsResetPasswordDialog({ vm }: { vm: AdminsPageVm }) {
  const { resetId, setResetId, newPassword, setNewPassword, onResetPassword } = vm;
  if (!resetId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="card w-full max-w-sm p-4">
        <h3 className="font-semibold text-ink">重置密码</h3>
        <input
          className="input-field mt-3 w-full"
          type="password"
          placeholder="新密码（至少 6 位）"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => setResetId(null)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void onResetPassword()}>
            确认
          </button>
        </div>
      </div>
    </div>
  );
}

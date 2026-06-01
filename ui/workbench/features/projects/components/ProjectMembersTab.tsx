"use client";

import { useState } from "react";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { MEMBER_ROLE_LABELS } from "@/features/projects/lib/biz-labels";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectMembersTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { members, users, addMember, removeMember } = vm;
  const { canWriteProject } = useBizPermissions();
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("viewer");
  const [saving, setSaving] = useState(false);

  const memberIds = new Set(members.map((m) => m.user_id));
  const availableUsers = users.filter((u) => !memberIds.has(u.id));

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;
    setSaving(true);
    try {
      await addMember(userId, role);
      setUserId("");
      setRole("viewer");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-4 space-y-4">
      {canWriteProject && (
        <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-[12rem] flex-1">
          <span className="text-xs text-ink-muted">用户</span>
          <select className="input-field mt-1 w-full text-sm" value={userId} onChange={(e) => setUserId(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {availableUsers.map((u) => <option key={u.id} value={u.id}>{u.username}{u.email ? ` (${u.email})` : ""}</option>)}
          </select>
        </label>
        <label>
          <span className="text-xs text-ink-muted">角色</span>
          <select className="input-field mt-1 text-sm" value={role} onChange={(e) => setRole(e.target.value)}>
            {Object.entries(MEMBER_ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <button type="submit" disabled={saving || !userId || availableUsers.length === 0} className="btn-primary text-sm">
          {saving ? "添加中…" : "添加成员"}
        </button>
        </form>
      )}

      {members.length === 0 ? <p className="text-sm text-ink-faint">暂无项目成员</p> : (
        <div className="space-y-2">
          {members.map((m) => (
            <div key={m.user_id} className="card flex items-center justify-between p-3 text-sm">
              <div>
                <span className="font-medium text-ink">{m.username ?? m.user_id.slice(0, 8)}</span>
                <span className="ml-2 rounded bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">{MEMBER_ROLE_LABELS[m.role_in_project] ?? m.role_in_project}</span>
              </div>
              {canWriteProject && (
                <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => void removeMember(m.user_id)}>移除</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

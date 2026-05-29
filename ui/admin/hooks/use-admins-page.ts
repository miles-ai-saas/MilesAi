"use client";

import { useCallback, useEffect, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi } from "@/lib/api";
import { useAdminAuthStore, useRequireAdmin } from "@/lib/auth-store";

export function useAdminsPage() {
  const ready = useRequireAdmin();
  const currentRole = useAdminAuthStore((s) => s.admin?.role);
  const currentId = useAdminAuthStore((s) => s.admin?.id);
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("ops");
  const [resetId, setResetId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listAdmins(p, s), []),
    { enabled: ready && currentRole === "super_admin" },
  );

  useEffect(() => {
    if (list.error) setErr(list.error);
  }, [list.error]);

  const forbidden = ready && currentRole !== "super_admin";

  const onCreate = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.createAdmin({
        username: username.trim(),
        password,
        display_name: displayName.trim() || undefined,
        role,
      });
      setShowForm(false);
      setUsername("");
      setPassword("");
      setDisplayName("");
      setMsg("管理员已创建");
      await list.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    }
  };

  const onDisable = async (id: string) => {
    if (!confirm("确定禁用该管理员？")) return;
    setErr("");
    try {
      await adminApi.disableAdmin(id);
      setMsg("已禁用");
      await list.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    }
  };

  const onResetPassword = async () => {
    if (!resetId || !newPassword) return;
    setErr("");
    try {
      await adminApi.resetAdminPassword(resetId, newPassword);
      setResetId(null);
      setNewPassword("");
      setMsg("密码已重置");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重置失败");
    }
  };

  return {
    forbidden,
    showForm,
    setShowForm,
    username,
    setUsername,
    password,
    setPassword,
    displayName,
    setDisplayName,
    role,
    setRole,
    resetId,
    setResetId,
    newPassword,
    setNewPassword,
    msg,
    err,
    list,
    currentId,
    onCreate,
    onDisable,
    onResetPassword,
  };
}

export type AdminsPageVm = ReturnType<typeof useAdminsPage>;

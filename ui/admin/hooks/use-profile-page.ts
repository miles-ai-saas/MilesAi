"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { adminApi } from "@/lib/api";
import { useAdminAuthStore, useRequireAdmin } from "@/lib/auth-store";

export function useProfilePage() {
  const ready = useRequireAdmin();
  const router = useRouter();
  const currentAdmin = useAdminAuthStore((s) => s.admin);
  const [me, setMe] = useState<{ username: string; role: string } | null>(null);
  const [sessions, setSessions] = useState<{ admin_id: string; username: string; role: string; is_current: boolean }[]>([]);
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [revoking, setRevoking] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [m, s] = await Promise.all([adminApi.me(), adminApi.listSessions()]);
    setMe(m);
    setSessions(s);
  }, []);

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready, reload]);

  const changePwd = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.changePassword(oldPwd, newPwd);
      await adminApi.logout();
      router.push("/login?msg=password_changed");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "修改失败");
    }
  };

  const revokeSession = async (adminId: string) => {
    setRevoking(adminId);
    setErr("");
    try {
      await adminApi.revokeSession(adminId);
      if (adminId === currentAdmin?.id) {
        await adminApi.logout();
        router.push("/login");
        return;
      }
      await reload();
      setMsg("会话已下线");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setRevoking(null);
    }
  };

  return {
    me,
    sessions,
    oldPwd,
    setOldPwd,
    newPwd,
    setNewPwd,
    msg,
    err,
    revoking,
    changePwd,
    revokeSession,
  };
}

export type ProfilePageVm = ReturnType<typeof useProfilePage>;

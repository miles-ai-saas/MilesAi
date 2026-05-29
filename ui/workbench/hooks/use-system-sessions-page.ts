"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { UserSession } from "@/lib/types";

export function useSystemSessionsPage() {
  const { ready } = useRequireAuth();
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setMsg("");
    try {
      setSessions(await api.listMySessions());
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  const revoke = async (jti: string) => {
    setMsg("");
    try {
      await api.revokeMySession(jti);
      setMsg("已强制下线该设备");
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  const revokeOthers = async () => {
    setMsg("");
    try {
      const res = await api.revokeOtherSessions();
      setMsg(`已下线其他 ${res.revoked} 个会话`);
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    }
  };

  return {
    sessions,
    loading,
    msg,
    load,
    revoke,
    revokeOthers,
  };
}

export type SystemSessionsPageVm = ReturnType<typeof useSystemSessionsPage>;

"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { ConfigDefinition, InfraStatus, TenantObjectStorageConfig } from "@/lib/types";

export function useSystemConfigLoad() {
  const { ready, user } = useRequireAuth();
  const [defs, setDefs] = useState<ConfigDefinition[]>([]);
  const [infra, setInfra] = useState<InfraStatus | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [oss, setOss] = useState<TenantObjectStorageConfig | null>(null);

  const reloadInfra = async () => {
    const status = await api.getInfraStatus();
    setInfra(status);
  };

  const reloadOss = async () => {
    const cfg = await api.getTenantObjectStorage();
    setOss(cfg);
    return cfg;
  };

  const reload = async () => {
    const d = await api.listConfigDefinitions();
    setDefs(d);
    await reloadInfra();
    await reloadOss().catch(() => undefined);
    const init: Record<string, string> = {};
    for (const item of d) {
      const v = item.default_value;
      init[item.key] = v == null ? "" : String(v);
    }
    setValues(init);
  };

  useEffect(() => {
    if (!ready) return;
    void reload().catch(() => undefined);
  }, [ready]);

  const onSave = async (key: string) => {
    setMsg("");
    const raw = values[key] ?? "";
    const num = Number(raw);
    const payload = Number.isFinite(num) && raw.trim() !== "" && /^-?\d+(\.\d+)?$/.test(raw.trim()) ? num : raw;
    await api.upsertSystemConfig(key, payload);
    setMsg(`已保存 ${key}`);
    await reload();
  };

  const byCategory = useMemo(
    () =>
      defs.reduce<Record<string, ConfigDefinition[]>>((acc, d) => {
        (acc[d.category] ??= []).push(d);
        return acc;
      }, {}),
    [defs],
  );

  return {
    user,
    infra,
    setInfra,
    oss,
    setOss,
    values,
    setValues,
    msg,
    setMsg,
    byCategory,
    onSave,
    reloadOss,
  };
}

export type SystemConfigLoadSlice = ReturnType<typeof useSystemConfigLoad>;

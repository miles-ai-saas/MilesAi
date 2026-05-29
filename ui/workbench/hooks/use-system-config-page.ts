"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { ConfigDefinition, InfraStatus, TenantObjectStorageConfig } from "@/lib/types";

const emptyOssForm = () => ({
  is_enabled: false,
  endpoint: "",
  bucket: "",
  access_key: "",
  secret_key: "",
  secure: false,
  region: "",
});

export function useSystemConfigPage() {
  const { ready, user } = useRequireAuth();
  const [defs, setDefs] = useState<ConfigDefinition[]>([]);
  const [infra, setInfra] = useState<InfraStatus | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [testing, setTesting] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [oss, setOss] = useState<TenantObjectStorageConfig | null>(null);
  const [ossForm, setOssForm] = useState(emptyOssForm);
  const [ossTesting, setOssTesting] = useState(false);
  const [ossSaving, setOssSaving] = useState(false);

  const reloadInfra = async () => {
    const status = await api.getInfraStatus();
    setInfra(status);
  };

  const reloadOss = async () => {
    const cfg = await api.getTenantObjectStorage();
    setOss(cfg);
    setOssForm({
      is_enabled: cfg.is_enabled,
      endpoint: cfg.endpoint ?? "",
      bucket: cfg.bucket ?? "",
      access_key: cfg.access_key ?? "",
      secret_key: "",
      secure: cfg.secure ?? false,
      region: cfg.region ?? "",
    });
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

  const onSaveOss = async () => {
    setOssSaving(true);
    setMsg("");
    try {
      const saved = await api.upsertTenantObjectStorage({
        is_enabled: ossForm.is_enabled,
        endpoint: ossForm.endpoint.trim(),
        bucket: ossForm.bucket.trim(),
        access_key: ossForm.access_key.trim(),
        secret_key: ossForm.secret_key.trim() || undefined,
        secure: ossForm.secure,
        region: ossForm.region.trim() || undefined,
      });
      setOss(saved);
      setOssForm((f) => ({ ...f, secret_key: "" }));
      setMsg(saved.is_enabled ? "已启用租户自有对象存储，新上传将写入您的 bucket" : "已保存：继续使用平台默认对象存储");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setOssSaving(false);
    }
  };

  const onTestOss = async () => {
    setOssTesting(true);
    setMsg("");
    try {
      const res = await api.testTenantObjectStorage({
        is_enabled: ossForm.is_enabled,
        endpoint: ossForm.endpoint.trim(),
        bucket: ossForm.bucket.trim(),
        access_key: ossForm.access_key.trim(),
        secret_key: ossForm.secret_key.trim() || undefined,
        secure: ossForm.secure,
        region: ossForm.region.trim() || undefined,
      });
      setMsg(res.ok ? res.message : `连接失败：${res.message}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setOssTesting(false);
    }
  };

  const onTestAll = async () => {
    setTesting(true);
    setTestingId(null);
    try {
      const res = await api.testInfraConnection();
      setInfra((prev) => (prev ? { ...prev, components: res.results, healthy: res.results.every((c) => c.status === "ok") } : prev));
      setMsg("连接测试完成");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
    }
  };

  const onTestOne = async (componentId: string) => {
    setTesting(true);
    setTestingId(componentId);
    try {
      const res = await api.testInfraConnection([componentId]);
      const updated = res.results[0];
      if (updated) {
        setInfra((prev) =>
          prev
            ? {
                ...prev,
                components: prev.components.map((c) => (c.id === componentId ? updated : c)),
                healthy: prev.components.map((c) => (c.id === componentId ? updated : c)).every((c) => c.status === "ok"),
              }
            : prev,
        );
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "连接测试失败");
    } finally {
      setTesting(false);
      setTestingId(null);
    }
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
    oss,
    ossForm,
    setOssForm,
    ossTesting,
    ossSaving,
    values,
    setValues,
    msg,
    testing,
    testingId,
    byCategory,
    onSave,
    onSaveOss,
    onTestOss,
    onTestAll,
    onTestOne,
  };
}

export type SystemConfigPageVm = ReturnType<typeof useSystemConfigPage>;

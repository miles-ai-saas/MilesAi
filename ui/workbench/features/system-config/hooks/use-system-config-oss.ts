"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { emptyOssForm } from "@/lib/system-config-shared";
import type { SystemConfigLoadSlice } from "@/hooks/use-system-config-load";

export function useSystemConfigOss({ setOss, setMsg }: Pick<SystemConfigLoadSlice, "setOss" | "setMsg">) {
  const [ossForm, setOssForm] = useState(emptyOssForm);
  const [ossTesting, setOssTesting] = useState(false);
  const [ossSaving, setOssSaving] = useState(false);

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

  return {
    ossForm,
    setOssForm,
    ossTesting,
    ossSaving,
    onSaveOss,
    onTestOss,
  };
}

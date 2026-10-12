"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useModelCatalogPage() {
  const ready = useRequireAdmin();
  const [vendor, setVendor] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("{\n  \"items\": [],\n  \"upsert\": true\n}\n");
  const [importBusy, setImportBusy] = useState(false);
  const [importMsg, setImportMsg] = useState("");
  const [importErr, setImportErr] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listModelCatalog(p, s, vendor || undefined), [vendor]),
    { enabled: ready, resetKey: vendor },
  );

  const onImport = async () => {
    setImportBusy(true);
    setImportErr("");
    setImportMsg("");
    try {
      const parsed = JSON.parse(importText) as { items?: Record<string, unknown>[]; upsert?: boolean };
      if (!parsed.items || !Array.isArray(parsed.items) || parsed.items.length === 0) {
        throw new Error("JSON 须含非空 items 数组");
      }
      const result = await adminApi.importModelCatalog({
        items: parsed.items,
        upsert: parsed.upsert !== false,
      });
      setImportMsg(
        `导入完成：新建 ${result.created}，更新 ${result.updated}，跳过 ${result.skipped}` +
          (result.errors.length ? `；错误 ${result.errors.length} 条` : ""),
      );
      await list.reload();
    } catch (e) {
      setImportErr(e instanceof Error ? e.message : "导入失败");
    } finally {
      setImportBusy(false);
    }
  };

  return {
    vendor,
    setVendor,
    list,
    importOpen,
    setImportOpen,
    importText,
    setImportText,
    importBusy,
    importMsg,
    importErr,
    onImport,
  };
}

export type ModelCatalogPageVm = ReturnType<typeof useModelCatalogPage>;

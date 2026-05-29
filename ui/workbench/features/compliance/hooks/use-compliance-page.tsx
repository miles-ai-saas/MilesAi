"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useComplianceMeta } from "@/features/compliance/hooks/use-compliance-meta";
import { sensitiveActionLabel } from "@/features/compliance/lib/compliance-labels";
import { filterBySearch } from "@/lib/filter-search";
import type { WordLibrary } from "@/lib/types";

export type ComplianceTab = "words" | "logs" | "test";

const COMPLIANCE_MAIN_TABS: { key: ComplianceTab; label: string }[] = [
  { key: "words", label: "敏感词库" },
  { key: "logs", label: "拦截日志" },
  { key: "test", label: "在线检测" },
];

const COMPLIANCE_PAGE_DESC = "按词库管理敏感词条；须在「参与扫描的词库」中勾选后，对话等环节才会进行检测。";

export function useCompliancePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const libraryId = searchParams.get("library");
  const { ready } = useRequireAuth();
  const complianceMeta = useComplianceMeta(ready);
  const [tab, setTab] = useState<ComplianceTab>("words");
  const [search, setSearch] = useState("");
  const [libDialogOpen, setLibDialogOpen] = useState(false);
  const [editingLib, setEditingLib] = useState<WordLibrary | null>(null);
  const [testText, setTestText] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [scanResult, setScanResult] = useState<{
    blocked: boolean;
    warned: boolean;
    scanning_enabled: boolean;
    matches: { word: string; action: string }[];
  } | null>(null);

  const actionLabel = (action: string) => sensitiveActionLabel(action, complianceMeta);

  const libraries = usePagedList(useCallback((p, s) => api.listWordLibraries(p, s), []), {
    enabled: ready && tab === "words" && !libraryId,
  });
  const logs = usePagedList(useCallback((p, s) => api.listInterceptLogs(p, s), []), {
    enabled: ready && tab === "logs",
  });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filteredLibs = useMemo(() => filterBySearch(libraries.items, search, (l) => `${l.name} ${l.description ?? ""}`), [libraries.items, search]);

  const [fetchedLibrary, setFetchedLibrary] = useState<WordLibrary | null>(null);

  useEffect(() => {
    if (!libraryId || !ready) {
      setFetchedLibrary(null);
      return;
    }
    const inList = libraries.items.find((l) => l.id === libraryId);
    if (inList) {
      setFetchedLibrary(inList);
      return;
    }
    void api
      .getWordLibrary(libraryId)
      .then(setFetchedLibrary)
      .catch(() => {
        const params = new URLSearchParams(searchParams.toString());
        params.delete("library");
        router.push(`/workbench/compliance?${params.toString()}`);
      });
  }, [libraryId, ready, libraries.items, router, searchParams]);

  const activeLibrary = useMemo(() => {
    if (!libraryId) return null;
    return libraries.items.find((l) => l.id === libraryId) ?? fetchedLibrary;
  }, [libraries.items, libraryId, fetchedLibrary]);

  const filteredLogs = useMemo(
    () => filterBySearch(logs.items, search, (l) => `${l.module} ${l.matched_word ?? ""} ${l.content_snippet ?? ""}`),
    [logs.items, search],
  );

  const openLibrary = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("library", id);
    router.push(`/workbench/compliance?${params.toString()}`);
  };

  const closeLibrary = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("library");
    router.push(`/workbench/compliance?${params.toString()}`);
  };

  const reloadLibraries = () => void libraries.reload();

  const onDeleteLibrary = (lib: WordLibrary) => {
    requestConfirm({
      title: "删除词库",
      message: (
        <>
          确定删除词库 <span className="font-medium">{lib.name}</span>？库内词条关联将一并移除。
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteWordLibrary(lib.id);
        if (libraryId === lib.id) closeLibrary();
        await libraries.reload();
      },
    });
  };

  const onScan = async () => {
    if (!testText.trim()) return;
    setScanBusy(true);
    try {
      setScanResult(await api.scanCompliance(testText.trim()));
    } finally {
      setScanBusy(false);
    }
  };

  const openCreateLib = () => {
    setEditingLib(null);
    setLibDialogOpen(true);
  };

  const openEditLib = (lib: WordLibrary) => {
    setEditingLib(lib);
    setLibDialogOpen(true);
  };

  const onTabChange = (k: string) => {
    setTab(k as ComplianceTab);
    closeLibrary();
  };

  return {
    tab,
    setTab,
    onTabChange,
    layoutShell: {
      title: "合规与安全",
      description: COMPLIANCE_PAGE_DESC,
      tabs: COMPLIANCE_MAIN_TABS,
      activeTab: tab,
      onTabChange,
    },
    search,
    setSearch,
    libraryId,
    complianceMeta,
    actionLabel,
    libraries,
    logs,
    filteredLibs,
    filteredLogs,
    activeLibrary,
    libDialogOpen,
    setLibDialogOpen,
    editingLib,
    testText,
    setTestText,
    scanBusy,
    scanResult,
    confirmDialog,
    openLibrary,
    closeLibrary,
    reloadLibraries,
    onDeleteLibrary,
    onScan,
    openCreateLib,
    openEditLib,
  };
}

export type CompliancePageVm = ReturnType<typeof useCompliancePage>;

"use client";

/** 合规词库（链路 §13）：词库/日志/试扫 + `useComplianceMeta`。 */

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ComplianceLibraryDetail } from "@/components/compliance/ComplianceLibraryDetail";
import { ComplianceScanBindingsPanel } from "@/components/compliance/ComplianceScanBindingsPanel";
import { WordLibraryDialog } from "@/components/compliance/WordLibraryDialog";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { sensitiveActionLabel } from "@/lib/compliance-labels";
import { filterBySearch } from "@/lib/filter-search";
import { useComplianceMeta } from "@/hooks/use-compliance-meta";
import type { InterceptLog, WordLibrary } from "@/lib/types";

type Tab = "words" | "logs" | "test";

/** 纯 UI Tab，不进 GET /compliance/meta */
const MAIN_TABS: { key: Tab; label: string }[] = [
  { key: "words", label: "敏感词库" },
  { key: "logs", label: "拦截日志" },
  { key: "test", label: "在线检测" },
];

const PAGE_DESC = "按词库管理敏感词条；须在「参与扫描的词库」中勾选后，对话等环节才会进行检测。";

function ScanStatusBadge({ blocked, warned, scanningEnabled }: { blocked: boolean; warned: boolean; scanningEnabled: boolean }) {
  if (!scanningEnabled) {
    return (
      <span className="inline-flex items-center rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-ink-muted ring-1 ring-line">
        扫描未启用
      </span>
    );
  }
  if (blocked) {
    return <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">将拦截</span>;
  }
  if (warned) {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">警告</span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">通过</span>
  );
}

function CompliancePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const libraryId = searchParams.get("library");
  const { ready } = useRequireAuth();
  const complianceMeta = useComplianceMeta(ready);
  const [tab, setTab] = useState<Tab>("words");
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

  const libraries = usePagedList(
    useCallback((p, s) => api.listWordLibraries(p, s), []),
    {
      enabled: ready && tab === "words" && !libraryId,
    },
  );
  const logs = usePagedList(
    useCallback((p, s) => api.listInterceptLogs(p, s), []),
    {
      enabled: ready && tab === "logs",
    },
  );
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

  if (tab === "logs") {
    return (
      <>
        <ResourceListLayout
          title="合规与安全"
          description={PAGE_DESC}
          searchPlaceholder="搜索模块、命中词或内容摘要"
          search={search}
          onSearchChange={setSearch}
          tabs={MAIN_TABS}
          activeTab={tab}
          onTabChange={(k) => setTab(k as Tab)}
          loading={logs.loading}
          footer={
            !logs.loading ? (
              <ResourceListFooter page={logs.page} size={logs.size} total={logs.total} onPageChange={logs.setPage} onSizeChange={logs.setSize} />
            ) : null
          }
        >
          <div className="col-span-full space-y-3">
            {!logs.loading && filteredLogs.length === 0 && (
              <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无拦截记录</p>
            )}
            {filteredLogs.map((l: InterceptLog) => (
              <article key={l.id} className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="font-medium text-ink">{l.module}</span>
                    <span className="badge bg-brand-light text-brand">{l.direction === "in" ? "输入" : "输出"}</span>
                    <span className={`badge ${l.action === "block" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"}`}>{actionLabel(l.action)}</span>
                    {l.matched_word && <span className="text-sm text-brand">命中「{l.matched_word}」</span>}
                  </div>
                  <time className="shrink-0 font-mono text-xs text-ink-faint">{new Date(l.created_at).toLocaleString("zh-CN")}</time>
                </div>
                {l.content_snippet && (
                  <p className="mt-3 rounded-lg bg-surface-muted px-3 py-2 text-sm leading-relaxed text-ink-muted line-clamp-3">{l.content_snippet}</p>
                )}
              </article>
            ))}
          </div>
        </ResourceListLayout>
      </>
    );
  }

  if (tab === "test") {
    return (
      <ResourceListLayout
        title="合规与安全"
        description={PAGE_DESC}
        search=""
        onSearchChange={() => {}}
        showSearch={false}
        tabs={MAIN_TABS}
        activeTab={tab}
        onTabChange={(k) => setTab(k as Tab)}
      >
        <div className="col-span-full mx-auto w-full max-w-2xl">
          <section className="rounded-xl border border-line bg-surface p-6 shadow-panel">
            <h2 className="text-base font-semibold text-ink">敏感词在线检测</h2>
            <p className="mt-1 text-sm text-ink-muted">使用当前「参与扫描的词库」试跑；未绑定词库时不会命中任何规则。</p>
            <textarea
              className="input-field mt-4 min-h-[140px] w-full resize-y"
              placeholder="粘贴或输入待检测文本…"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
            />
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button type="button" className="btn-primary" disabled={scanBusy || !testText.trim()} onClick={() => void onScan()}>
                {scanBusy ? "检测中…" : "开始检测"}
              </button>
              {scanResult && <ScanStatusBadge blocked={scanResult.blocked} warned={scanResult.warned} scanningEnabled={scanResult.scanning_enabled} />}
            </div>
            {scanResult && (
              <div className="mt-5 rounded-lg border border-line-soft bg-surface-muted p-4">
                {!scanResult.scanning_enabled ? (
                  <p className="text-sm text-ink-muted">未配置参与扫描的词库，本次检测跳过。</p>
                ) : scanResult.matches.length > 0 ? (
                  <ul className="flex flex-wrap gap-2">
                    {scanResult.matches.map((m, i) => (
                      <li
                        key={`${m.word}-${i}`}
                        className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
                          m.action === "block" ? "bg-red-50 text-red-700 ring-1 ring-red-100" : "bg-amber-50 text-amber-800 ring-1 ring-amber-100"
                        }`}
                      >
                        {m.word}
                        <span className="ml-1 opacity-70">· {actionLabel(m.action)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-ink-muted">未命中任何敏感词规则。</p>
                )}
              </div>
            )}
          </section>
        </div>
      </ResourceListLayout>
    );
  }

  if (libraryId && !activeLibrary) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-ink-muted">加载词库…</div>;
  }

  if (libraryId && activeLibrary) {
    return (
      <ResourceListLayout
        title="合规与安全"
        description={PAGE_DESC}
        search=""
        onSearchChange={() => {}}
        showSearch={false}
        tabs={MAIN_TABS}
        activeTab={tab}
        onTabChange={(k) => setTab(k as Tab)}
      >
        <ComplianceLibraryDetail
          library={activeLibrary}
          sensitiveActions={complianceMeta?.sensitive_actions}
          onBack={closeLibrary}
          onLibraryChange={reloadLibraries}
        />
      </ResourceListLayout>
    );
  }

  return (
    <>
      <ResourceListLayout
        title="合规与安全"
        description={PAGE_DESC}
        searchPlaceholder="搜索词库名称"
        search={search}
        onSearchChange={setSearch}
        tabs={MAIN_TABS}
        activeTab={tab}
        onTabChange={(k) => {
          setTab(k as Tab);
          closeLibrary();
        }}
        loading={libraries.loading && !libraryId}
        headerAction={
          <button
            type="button"
            className="btn-sm-primary"
            onClick={() => {
              setEditingLib(null);
              setLibDialogOpen(true);
            }}
          >
            新建词库
          </button>
        }
        footer={
          !libraries.loading && !libraryId ? (
            <ResourceListFooter
              page={libraries.page}
              size={libraries.size}
              total={libraries.total}
              onPageChange={libraries.setPage}
              onSizeChange={libraries.setSize}
            />
          ) : null
        }
      >
        <ComplianceScanBindingsPanel onSaved={reloadLibraries} />
        <AddResourceCard
          label="新建词库"
          hint="创建后可添加词条并勾选参与扫描"
          onClick={() => {
            setEditingLib(null);
            setLibDialogOpen(true);
          }}
        />
        {filteredLibs.map((lib) => (
          <ResourceItemCard
            key={lib.id}
            title={lib.name}
            description={lib.description ?? "点击管理库内敏感词条"}
            badge={lib.is_active ? "启用" : "停用"}
            muted={!lib.is_active}
            onClick={() => openLibrary(lib.id)}
            meta={<span className="tabular-nums text-ink-muted">{lib.word_count} 条词条</span>}
            actions={
              <CardActions
                onView={() => openLibrary(lib.id)}
                onEdit={() => {
                  setEditingLib(lib);
                  setLibDialogOpen(true);
                }}
                onDelete={() => onDeleteLibrary(lib)}
              />
            }
          />
        ))}
      </ResourceListLayout>

      <WordLibraryDialog open={libDialogOpen} library={editingLib} onClose={() => setLibDialogOpen(false)} onSaved={reloadLibraries} />
      {confirmDialog}
    </>
  );
}

export default function CompliancePage() {
  return (
    <Suspense fallback={<div className="flex min-h-[40vh] items-center justify-center text-sm text-ink-muted">加载合规页面…</div>}>
      <CompliancePageContent />
    </Suspense>
  );
}

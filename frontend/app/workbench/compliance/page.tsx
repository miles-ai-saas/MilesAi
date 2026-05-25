"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import type { InterceptLog, SensitiveWord } from "@/lib/types";

type Tab = "words" | "logs" | "test";

const MAIN_TABS: { key: Tab; label: string }[] = [
  { key: "words", label: "敏感词库" },
  { key: "logs", label: "拦截日志" },
  { key: "test", label: "在线检测" },
];

const PAGE_DESC =
  "敏感词在智能体对话等环节自动检测；命中拦截或警告规则会写入审计日志，可在本页维护词库与试检。";

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

function ScanStatusBadge({
  blocked,
  warned,
}: {
  blocked: boolean;
  warned: boolean;
}) {
  if (blocked) {
    return (
      <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">
        将拦截
      </span>
    );
  }
  if (warned) {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
        警告
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">
      通过
    </span>
  );
}

export default function CompliancePage() {
  const { ready } = useRequireAuth();
  const [tab, setTab] = useState<Tab>("words");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [newWord, setNewWord] = useState("");
  const [category, setCategory] = useState("");
  const [action, setAction] = useState<"warn" | "block">("block");
  const [batchText, setBatchText] = useState("");
  const [testText, setTestText] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [scanResult, setScanResult] = useState<{
    blocked: boolean;
    warned: boolean;
    matches: { word: string; action: string }[];
  } | null>(null);

  const words = usePagedList(useCallback((p, s) => api.listSensitiveWords(p, s), []), {
    enabled: ready && tab === "words",
  });
  const logs = usePagedList(useCallback((p, s) => api.listInterceptLogs(p, s), []), {
    enabled: ready && tab === "logs",
  });

  const filteredWords = useMemo(
    () => filterBySearch(words.items, search, (w) => `${w.word} ${w.category ?? ""}`),
    [words.items, search],
  );

  const filteredLogs = useMemo(
    () =>
      filterBySearch(
        logs.items,
        search,
        (l) => `${l.module} ${l.matched_word ?? ""} ${l.content_snippet ?? ""}`,
      ),
    [logs.items, search],
  );

  const wordStats = useMemo(() => {
    const active = words.items.filter((w) => w.is_active).length;
    const block = words.items.filter((w) => w.action === "block").length;
    const warn = words.items.filter((w) => w.action === "warn").length;
    return { active, block, warn };
  }, [words.items]);

  const onBatchImport = async () => {
    const lines = batchText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!lines.length) return;
    const batch = lines.map((line) => {
      const [word, act, cat] = line.split(",").map((s) => s.trim());
      return {
        word,
        action: (act === "warn" ? "warn" : "block") as "warn" | "block",
        category: cat || undefined,
      };
    });
    await api.batchCreateSensitiveWords(batch);
    setBatchText("");
    setBatchOpen(false);
    await words.reload();
  };

  const onCreate = async () => {
    if (!newWord.trim()) return;
    await api.createSensitiveWord(newWord.trim(), action, category.trim() || undefined);
    setNewWord("");
    setCategory("");
    setDialogOpen(false);
    await words.reload();
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

  const addWordDialog = (
    <ResourceDialog
      open={dialogOpen}
      title="添加敏感词"
      onClose={() => setDialogOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={onCreate}>
            确定
          </button>
        </>
      }
    >
      <label className="block space-y-1">
        <span className="text-xs text-ink-muted">敏感词</span>
        <input
          className="input-field w-full"
          placeholder="例如：违禁品"
          value={newWord}
          onChange={(e) => setNewWord(e.target.value)}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs text-ink-muted">分类（可选）</span>
        <input
          className="input-field w-full"
          placeholder="例如：安全"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs text-ink-muted">处置方式</span>
        <select
          className="input-field w-full"
          value={action}
          onChange={(e) => setAction(e.target.value as "warn" | "block")}
        >
          <option value="warn">警告（记录日志）</option>
          <option value="block">拦截（拒绝请求）</option>
        </select>
      </label>
    </ResourceDialog>
  );

  const batchDialog = (
    <ResourceDialog
      open={batchOpen}
      title="批量导入敏感词"
      onClose={() => setBatchOpen(false)}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={() => setBatchOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={onBatchImport}>
            导入
          </button>
        </>
      }
    >
      <p className="text-xs leading-relaxed text-ink-muted">
        每行一条，格式：<span className="font-mono text-ink">词语,block,分类</span> 或{" "}
        <span className="font-mono text-ink">词语,warn</span>
      </p>
      <textarea
        className="input-field min-h-[160px] w-full font-mono text-xs"
        placeholder={"违禁品,block,安全\n内部资料,warn"}
        value={batchText}
        onChange={(e) => setBatchText(e.target.value)}
      />
    </ResourceDialog>
  );

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
              <ResourceListFooter
                page={logs.page}
                size={logs.size}
                total={logs.total}
                onPageChange={logs.setPage}
              />
            ) : null
          }
        >
          <div className="col-span-full space-y-3">
            {!logs.loading && filteredLogs.length === 0 && (
              <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
                暂无拦截记录
              </p>
            )}
            {filteredLogs.map((l: InterceptLog) => (
              <article
                key={l.id}
                className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="font-medium text-ink">{l.module}</span>
                    <span className="badge bg-brand-light text-brand">
                      {l.direction === "in" ? "输入" : "输出"}
                    </span>
                    <span
                      className={`badge ${
                        l.action === "block"
                          ? "bg-red-50 text-red-700"
                          : "bg-amber-50 text-amber-800"
                      }`}
                    >
                      {l.action === "block" ? "拦截" : "警告"}
                    </span>
                    {l.matched_word && (
                      <span className="text-sm text-brand">命中「{l.matched_word}」</span>
                    )}
                  </div>
                  <time className="shrink-0 font-mono text-xs text-ink-faint">
                    {new Date(l.created_at).toLocaleString("zh-CN")}
                  </time>
                </div>
                {l.content_snippet && (
                  <p className="mt-3 rounded-lg bg-surface-muted px-3 py-2 text-sm leading-relaxed text-ink-muted line-clamp-3">
                    {l.content_snippet}
                  </p>
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
      <>
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
              <p className="mt-1 text-sm text-ink-muted">
                模拟内容审核，不会阻断当前页面；命中 block 规则会写入拦截日志。
              </p>
              <textarea
                className="input-field mt-4 min-h-[140px] w-full resize-y"
                placeholder="粘贴或输入待检测文本…"
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  className="btn-primary"
                  disabled={scanBusy || !testText.trim()}
                  onClick={onScan}
                >
                  {scanBusy ? "检测中…" : "开始检测"}
                </button>
                {scanResult && (
                  <ScanStatusBadge blocked={scanResult.blocked} warned={scanResult.warned} />
                )}
              </div>
              {scanResult && (
                <div className="mt-5 rounded-lg border border-line-soft bg-surface-muted p-4">
                  {scanResult.matches.length > 0 ? (
                    <ul className="flex flex-wrap gap-2">
                      {scanResult.matches.map((m, i) => (
                        <li
                          key={`${m.word}-${i}`}
                          className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
                            m.action === "block"
                              ? "bg-red-50 text-red-700 ring-1 ring-red-100"
                              : "bg-amber-50 text-amber-800 ring-1 ring-amber-100"
                          }`}
                        >
                          {m.word}
                          <span className="ml-1 opacity-70">
                            · {m.action === "block" ? "拦截" : "警告"}
                          </span>
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
      </>
    );
  }

  return (
    <>
      <ResourceListLayout
        title="合规与安全"
        description={PAGE_DESC}
        searchPlaceholder="搜索敏感词或分类"
        search={search}
        onSearchChange={setSearch}
        tabs={MAIN_TABS}
        activeTab={tab}
        onTabChange={(k) => setTab(k as Tab)}
        loading={words.loading}
        headerAction={
          <button type="button" className="btn-ghost shrink-0" onClick={() => setBatchOpen(true)}>
            批量导入
          </button>
        }
        footer={
          !words.loading ? (
            <ResourceListFooter
              page={words.page}
              size={words.size}
              total={words.total}
              onPageChange={words.setPage}
            />
          ) : null
        }
      >
        <div className="col-span-full grid gap-3 sm:grid-cols-3">
          <StatChip label="词库总数" value={String(words.total)} hint="当前租户已配置" />
          <StatChip
            label="本页启用"
            value={String(wordStats.active)}
            hint={`拦截 ${wordStats.block} · 警告 ${wordStats.warn}`}
          />
          <StatChip label="本页展示" value={String(filteredWords.length)} hint="受搜索筛选影响" />
        </div>
        <AddResourceCard
          label="添加敏感词"
          hint="配置规则后自动应用于对话与内容输入"
          onClick={() => setDialogOpen(true)}
        />
        {filteredWords.map((w: SensitiveWord) => (
          <ResourceItemCard
            key={w.id}
            title={w.word}
            description={w.category ? `分类：${w.category}` : "用于对话与内容输入检测"}
            badge={w.action === "block" ? "拦截" : "警告"}
            meta={<span>{w.is_active ? "已启用" : "已停用"}</span>}
            actions={
              <span className="flex gap-3">
                <button
                  type="button"
                  className="text-xs text-brand hover:underline"
                  onClick={async (e) => {
                    e.stopPropagation();
                    await api.updateSensitiveWord(w.id, { is_active: !w.is_active });
                    await words.reload();
                  }}
                >
                  {w.is_active ? "停用" : "启用"}
                </button>
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline"
                  onClick={async (e) => {
                    e.stopPropagation();
                    await api.deleteSensitiveWord(w.id);
                    await words.reload();
                  }}
                >
                  删除
                </button>
              </span>
            }
          />
        ))}
      </ResourceListLayout>
      {addWordDialog}
      {batchDialog}
    </>
  );
}

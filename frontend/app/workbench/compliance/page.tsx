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

export default function CompliancePage() {
  const { ready } = useRequireAuth();
  const [tab, setTab] = useState<Tab>("words");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newWord, setNewWord] = useState("");
  const [category, setCategory] = useState("");
  const [action, setAction] = useState<"warn" | "block">("block");
  const [testText, setTestText] = useState("");
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

  const filtered = useMemo(
    () => filterBySearch(words.items, search, (w) => `${w.word} ${w.category ?? ""}`),
    [words.items, search],
  );

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
    setScanResult(await api.scanCompliance(testText.trim()));
    if (tab === "logs") await logs.reload();
  };

  const mainTabs: { key: Tab; label: string }[] = [
    { key: "words", label: "敏感词库" },
    { key: "logs", label: "拦截日志" },
    { key: "test", label: "检测试" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">合规与安全</h1>
        <p className="mt-1 text-sm text-ink-muted">
          敏感词在智能体对话等环节自动检测；拦截与警告会写入审计日志。
        </p>
        <div className="mt-4 flex rounded-lg border border-line bg-surface p-0.5">
          {mainTabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                tab === t.key
                  ? "bg-brand-light font-medium text-brand"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "words" && (
        <>
          <ResourceListLayout
            title="敏感词库"
            description=""
            searchPlaceholder="搜索敏感词"
            search={search}
            onSearchChange={setSearch}
            loading={words.loading}
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
            <AddResourceCard
              label="添加新敏感词"
              hint="配置敏感词规则用于内容审核"
              onClick={() => setDialogOpen(true)}
            />
            {filtered.map((w: SensitiveWord) => (
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
            <input
              className="input-field w-full"
              placeholder="敏感词"
              value={newWord}
              onChange={(e) => setNewWord(e.target.value)}
            />
            <input
              className="input-field w-full"
              placeholder="分类（可选）"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            />
            <select
              className="input-field w-full"
              value={action}
              onChange={(e) => setAction(e.target.value as "warn" | "block")}
            >
              <option value="warn">警告（记录日志）</option>
              <option value="block">拦截（拒绝请求）</option>
            </select>
          </ResourceDialog>
        </>
      )}

      {tab === "logs" && (
        <section className="card p-4">
          <h2 className="text-sm font-semibold text-ink">拦截日志</h2>
          {logs.loading && <p className="mt-3 text-sm text-ink-muted">加载中…</p>}
          <ul className="mt-3 max-h-[28rem] space-y-2 overflow-y-auto text-sm">
            {!logs.loading && logs.items.length === 0 && (
              <li className="text-ink-faint">暂无拦截记录</li>
            )}
            {logs.items.map((l: InterceptLog) => (
              <li key={l.id} className="rounded-lg border border-line-soft bg-surface-muted px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-ink-faint">
                    {l.created_at.slice(0, 19)}
                  </span>
                  <span className="font-medium">{l.module}</span>
                  <span className="badge bg-brand-light text-brand">
                    {l.direction === "in" ? "输入" : "输出"}
                  </span>
                  <span className="badge bg-surface text-ink-muted">
                    {l.action === "block" ? "拦截" : "警告"}
                  </span>
                  {l.matched_word && (
                    <span className="text-brand">「{l.matched_word}」</span>
                  )}
                </div>
                {l.content_snippet && (
                  <p className="mt-1 text-xs text-ink-muted line-clamp-2">{l.content_snippet}</p>
                )}
              </li>
            ))}
          </ul>
          {!logs.loading && (
            <ResourceListFooter
              className="mt-4"
              page={logs.page}
              size={logs.size}
              total={logs.total}
              onPageChange={logs.setPage}
            />
          )}
        </section>
      )}

      {tab === "test" && (
        <section className="card mx-auto max-w-xl p-6">
          <h2 className="text-sm font-semibold text-ink">敏感词检测试</h2>
          <p className="mt-1 text-xs text-ink-muted">不会阻断页面，命中 block 规则会写入拦截日志。</p>
          <textarea
            className="input-field mt-4 min-h-[120px] w-full"
            placeholder="输入待检测文本…"
            value={testText}
            onChange={(e) => setTestText(e.target.value)}
          />
          <button type="button" className="btn-primary mt-3" onClick={onScan}>
            检测
          </button>
          {scanResult && (
            <div className="mt-4 rounded-lg bg-surface-muted p-3 text-sm">
              <p>
                结果：
                {scanResult.blocked ? (
                  <span className="text-red-600">将拦截</span>
                ) : scanResult.warned ? (
                  <span className="text-amber-600">警告</span>
                ) : (
                  <span className="text-emerald-600">通过</span>
                )}
              </p>
              {scanResult.matches.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-ink-muted">
                  {scanResult.matches.map((m, i) => (
                    <li key={i}>
                      {m.word} · {m.action === "block" ? "拦截" : "警告"}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

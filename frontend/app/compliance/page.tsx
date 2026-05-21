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
import type { SensitiveWord } from "@/lib/types";

export default function CompliancePage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newWord, setNewWord] = useState("");
  const [action, setAction] = useState<"warn" | "block">("block");

  const list = usePagedList(useCallback((p, s) => api.listSensitiveWords(p, s), []), {
    enabled: ready,
  });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (w) => w.word),
    [list.items, search],
  );

  const onCreate = async () => {
    if (!newWord.trim()) return;
    await api.createSensitiveWord(newWord.trim(), action);
    setNewWord("");
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="合规"
        description="维护敏感词库，在智能体对话等场景自动进行内容安全检测与拦截，保障业务合规。"
        searchPlaceholder="搜索敏感词"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
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
              <button
                type="button"
                className="text-xs text-red-600 hover:underline"
                onClick={async (e) => {
                  e.preventDefault();
                  await api.deleteSensitiveWord(w.id);
                  await list.reload();
                }}
              >
                删除
              </button>
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
        <select
          className="input-field w-full"
          value={action}
          onChange={(e) => setAction(e.target.value as "warn" | "block")}
        >
          <option value="warn">警告</option>
          <option value="block">拦截</option>
        </select>
      </ResourceDialog>
    </>
  );
}

"use client";

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { HooksPageVm } from "@/features/http-hooks/hooks/use-hooks-page";

const HOOKS_PAGE_DESC =
  "在智能体对话、流程运行、工具调用等节点挂载 HTTP 扩展，用于审计、鉴权、限流或对接外部系统。请求体为 Event v1 信封（含 trace_id）；before_* 钩子可返回 block / modify。敏感词拦截请使用合规模块。";

export function HookCatalogView({ vm }: { vm: HooksPageVm }) {
  const { list, search, setSearch, filtered, openCreate, openEdit, onDeleteHook, toggleActive, openBindings } = vm;

  return (
    <ResourceListLayout
      title="钩子"
      description={HOOKS_PAGE_DESC}
      searchPlaceholder="搜索钩子名称"
      search={search}
      onSearchChange={setSearch}
      loading={list.loading}
      footer={
        !list.loading ? (
          <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        ) : null
      }
    >
      <AddResourceCard label="新建 HTTP 钩子" hint="Webhook · 支持多条绑定规则" onClick={openCreate} />
      {filtered.map((h) => (
        <ResourceItemCard
          key={h.id}
          title={h.name}
          description={String((h.config as { url?: string }).url ?? "未配置 URL")}
          badge={h.hook_type}
          meta={
            <span className="text-xs text-ink-muted">
              {h.is_active ? "已启用" : "已停用"}
              {(h.config as { on_failure?: string }).on_failure === "fail_request" ? " · 失败时阻断" : ""}
            </span>
          }
          actions={
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="text-xs text-ink-muted hover:underline"
                onClick={(e) => {
                  e.stopPropagation();
                  void toggleActive(h);
                }}
              >
                {h.is_active ? "停用" : "启用"}
              </button>
              <CardActions onEdit={() => openEdit(h)} onDelete={() => onDeleteHook(h)} />
              <button type="button" className="text-xs text-brand hover:underline" onClick={() => void openBindings(h)}>
                绑定与记录
              </button>
            </div>
          }
        />
      ))}
    </ResourceListLayout>
  );
}

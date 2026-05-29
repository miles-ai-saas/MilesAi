"use client";

import { GenerativeJobsSection } from "@/features/tasks/components/GenerativeJobsSection";
import { TaskDetailDialog } from "@/features/tasks/components/TaskDetailDialog";
import { TaskRow } from "@/features/tasks/components/TaskRow";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import type { TasksPageVm } from "@/features/tasks/hooks/use-tasks-page";
import { TASK_CATEGORY_TABS } from "@/features/tasks/lib/task-labels";

const TASKS_PAGE_DESC = {
  celery: "文档入库等 Celery 异步任务；支持按状态筛选、搜索、取消与重试；点击「刷新」更新列表。",
  generative: "智能体对话、流程或 API 触发的生图/生视频任务；支持类型筛选、进度查看、取消与失败重试；可跳转关联的后台 Celery 记录；点击「刷新」更新列表。",
} as const;

function TaskCategorySwitcher({ category, onChange }: { category: TasksPageVm["category"]; onChange: (c: TasksPageVm["category"]) => void }) {
  return (
    <div className="mb-4 flex gap-2">
      {TASK_CATEGORY_TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            category === tab.key ? "bg-brand text-white shadow-sm" : "bg-surface text-ink-muted ring-1 ring-line hover:text-ink"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function TasksPageView({ vm }: { vm: TasksPageVm }) {
  const {
    category,
    setCategory,
    search,
    setSearch,
    filter,
    msg,
    setMsg,
    taskMeta,
    list,
    filtered,
    pageStats,
    statusTabs,
    onFilterChange,
    selectedTaskIds,
    cancellableOnPage,
    toggleTaskSelection,
    batchCancelSelected,
    detailTaskId,
    openDetail,
    closeDetail,
    act,
    isGenerative,
    listRefreshing,
    refreshList,
    ready,
    onGenerativeExposeList,
  } = vm;

  return (
    <ResourceListLayout
      title="任务中心"
      description={TASKS_PAGE_DESC[category]}
      showSearch={false}
      search={search}
      onSearchChange={setSearch}
      tabs={statusTabs}
      activeTab={filter}
      onTabChange={onFilterChange}
      loading={!isGenerative && list.loading}
      headerAction={
        <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
          <label className="relative block w-full sm:w-72">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint">
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
                  clipRule="evenodd"
                />
              </svg>
            </span>
            <input
              type="search"
              className="input w-full pl-9"
              placeholder={isGenerative ? "搜索 Prompt、ID 或错误信息" : "搜索任务名称、ID 或失败原因"}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <button type="button" className="btn-ghost shrink-0 text-sm" disabled={listRefreshing} onClick={refreshList}>
            {listRefreshing ? "刷新中…" : "刷新"}
          </button>
          {!isGenerative && selectedTaskIds.size > 0 ? (
            <button type="button" className="btn-sm-outline shrink-0 text-red-600" onClick={() => void batchCancelSelected()}>
              批量取消 ({selectedTaskIds.size})
            </button>
          ) : null}
        </div>
      }
      footer={
        !isGenerative && !list.loading ? (
          <ResourceListFooter page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        ) : null
      }
    >
      <div className="col-span-full -mt-2 mb-2">
        <TaskCategorySwitcher category={category} onChange={setCategory} />
      </div>

      {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}

      {isGenerative ? (
        <GenerativeJobsSection
          enabled={ready}
          search={search}
          filter={filter}
          msg={msg}
          onMsg={setMsg}
          onExposeList={onGenerativeExposeList}
        />
      ) : (
        <>
          <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatChip label="任务总数" value={String(list.total)} hint="当前筛选条件下" />
            <StatChip label="本页运行中" value={String(pageStats.running)} hint={`等待 ${pageStats.pending} · 失败 ${pageStats.failed}（当前页）`} />
            <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索筛选影响" />
          </div>

          <div className="col-span-full space-y-3">
            {!list.loading && filtered.length === 0 && (
              <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无匹配的任务</p>
            )}
            {cancellableOnPage.length > 0 && filtered.length > 0 ? (
              <p className="text-xs text-ink-faint">可勾选 {cancellableOnPage.length} 条待取消任务，使用右上角「批量取消」</p>
            ) : null}
            {filtered.map((t) => (
              <TaskRow
                key={t.id}
                task={t}
                taskMeta={taskMeta}
                selected={selectedTaskIds.has(t.id)}
                onSelectChange={(checked) => toggleTaskSelection(t.id, checked)}
                onViewDetail={() => openDetail(t.id)}
                onCancel={() => void act(t.id, "cancel")}
                onRetry={() => void act(t.id, "retry")}
              />
            ))}
          </div>

          <TaskDetailDialog open={!!detailTaskId} taskId={detailTaskId} taskMeta={taskMeta} onClose={closeDetail} onChanged={() => void list.reload()} />
        </>
      )}
    </ResourceListLayout>
  );
}

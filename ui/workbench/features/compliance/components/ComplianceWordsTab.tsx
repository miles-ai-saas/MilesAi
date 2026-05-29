"use client";

import { ComplianceLibraryDetail } from "@/features/compliance/components/ComplianceLibraryDetail";
import { ComplianceScanBindingsPanel } from "@/features/compliance/components/ComplianceScanBindingsPanel";
import { WordLibraryDialog } from "@/features/compliance/components/WordLibraryDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { CompliancePageVm } from "@/features/compliance/hooks/use-compliance-page";

export function ComplianceWordsTab({ vm }: { vm: CompliancePageVm }) {
  const {
    layoutShell,
    search,
    setSearch,
    libraryId,
    libraries,
    filteredLibs,
    activeLibrary,
    complianceMeta,
    libDialogOpen,
    setLibDialogOpen,
    editingLib,
    confirmDialog,
    openLibrary,
    closeLibrary,
    reloadLibraries,
    onDeleteLibrary,
    openCreateLib,
    openEditLib,
  } = vm;

  if (libraryId && !activeLibrary) {
    return <div className="flex min-h-[40vh] items-center justify-center text-sm text-ink-muted">加载词库…</div>;
  }

  if (libraryId && activeLibrary) {
    return (
      <ResourceListLayout
        {...layoutShell}
        search=""
        onSearchChange={() => {}}
        showSearch={false}
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
        {...layoutShell}
        searchPlaceholder="搜索词库名称"
        search={search}
        onSearchChange={setSearch}
        loading={libraries.loading && !libraryId}
        headerAction={
          <button type="button" className="btn-sm-primary" onClick={openCreateLib}>
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
        <AddResourceCard label="新建词库" hint="创建后可添加词条并勾选参与扫描" onClick={openCreateLib} />
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
                onEdit={() => openEditLib(lib)}
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

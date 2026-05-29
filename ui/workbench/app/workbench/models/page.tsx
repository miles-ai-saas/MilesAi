"use client";

/** 模型目录（链路 §3）：列表 + `GET /models/meta` → model-catalog-ui。 */

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { PageHeader } from "@/components/layout/PageHeader";
import { ModelCatalogGrid, ModelFilterPanel, useModelsPage, type ModelsPageVm } from "@/features/models";

const MODELS_PAGE_DESC =
  "内置模型由平台统一提供密钥，可直接选用；自定义 OpenAI 兼容接入需自行配置 API Key。";

function ModelsPageOverlays({ vm }: { vm: ModelsPageVm }) {
  return (
    <>
      <ResourceDialog
        open={vm.dialogOpen}
        title={vm.editing ? "编辑自定义模型" : "添加自定义模型"}
        size="lg"
        onClose={() => {
          vm.setDialogOpen(false);
          vm.setSaveError("");
        }}
        footer={
          <>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                vm.setDialogOpen(false);
                vm.setSaveError("");
              }}
            >
              取消
            </button>
            <button type="button" className="btn-primary" onClick={() => void vm.onSave()}>
              保存
            </button>
          </>
        }
      >
        {vm.saveError ? <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{vm.saveError}</p> : null}
        <p className="text-xs text-ink-muted">自定义模型由本租户自行维护接入参数；新建时必须填写 API Key，编辑时留空表示不修改密钥。</p>
        <input className="input-field w-full" placeholder="展示名称" value={vm.name} onChange={(e) => vm.setName(e.target.value)} />
        <select className="input-field w-full" value={vm.vendorField} onChange={(e) => vm.setVendorField(e.target.value)}>
          {vm.vendors.map((v) => (
            <option key={v.value} value={v.value}>
              {v.label}
            </option>
          ))}
          <option value="other">其它</option>
        </select>
        <input className="input-field w-full" placeholder="模型编码（可选）" value={vm.modelCode} onChange={(e) => vm.setModelCode(e.target.value)} />
        <input className="input-field w-full" placeholder="请求体 model 参数" value={vm.modelName} onChange={(e) => vm.setModelName(e.target.value)} />
        <select className="input-field w-full" value={vm.modelTypeField} onChange={(e) => vm.setModelTypeField(e.target.value)}>
          {(vm.meta?.model_types ?? []).map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <textarea
          className="input-field w-full min-h-[72px]"
          placeholder="描述（可选）"
          value={vm.description}
          onChange={(e) => vm.setDescription(e.target.value)}
        />
        <input className="input-field w-full" placeholder="API Base（可选）" value={vm.apiBase} onChange={(e) => vm.setApiBase(e.target.value)} />
        <input
          className="input-field w-full"
          placeholder={vm.editing ? "API Key（留空不修改）" : "API Key（必填）"}
          type="password"
          value={vm.apiKey}
          onChange={(e) => vm.setApiKey(e.target.value)}
        />
      </ResourceDialog>

      <ResourceDialog
        open={vm.credDialogOpen}
        title={vm.credTarget ? `租户自有 Key · ${vm.credTarget.name}` : "租户自有 Key"}
        onClose={() => vm.setCredDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => vm.setCredDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={() => void vm.onSaveCred()}>
              保存
            </button>
          </>
        }
      >
        <p className="text-xs text-ink-muted">
          内置模型默认使用平台统一密钥，无需租户配置。仅在合规或自付账单等场景下，可在此填写自有 Key（BYOK），将优先于平台密钥。
        </p>
        <input className="input-field w-full" placeholder="API Base（可选，留空用内置默认）" value={vm.apiBase} onChange={(e) => vm.setApiBase(e.target.value)} />
        <input className="input-field w-full" placeholder="租户 API Key（必填）" type="password" value={vm.apiKey} onChange={(e) => vm.setApiKey(e.target.value)} />
      </ResourceDialog>
      {vm.confirmDialog}
    </>
  );
}

export default function ModelsPage() {
  const vm = useModelsPage();

  return (
    <div className="resource-page-shell">
      <PageHeader
        title="模型供应商"
        description={MODELS_PAGE_DESC}
        action={
          <button type="button" className="btn-primary" onClick={vm.openCreate}>
            + 自定义模型
          </button>
        }
      />
      <ModelFilterPanel vm={vm} />
      <h2 className="mb-3 text-sm font-semibold text-ink">模型列表</h2>
      <ModelCatalogGrid vm={vm} />
      <ModelsPageOverlays vm={vm} />
    </div>
  );
}

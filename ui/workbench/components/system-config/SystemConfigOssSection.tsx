"use client";

import type { SystemConfigPageVm } from "@/hooks/use-system-config-page";

export function SystemConfigOssSection({ vm }: { vm: SystemConfigPageVm }) {
  const { oss, ossForm, setOssForm, ossTesting, ossSaving, onTestOss, onSaveOss } = vm;

  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">租户对象存储（L2 BYOK）</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            启用后，本租户知识库/附件/生成物新上传将使用您的 S3 兼容桶；历史文件仍在原桶。 当前：
            {oss?.source === "tenant" && oss.is_enabled ? "租户自有存储" : "平台默认存储"}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn-ghost text-sm" disabled={ossTesting || ossSaving} onClick={() => void onTestOss()}>
            {ossTesting ? "测试中…" : "测试连接"}
          </button>
          <button type="button" className="btn-primary text-sm" disabled={ossSaving} onClick={() => void onSaveOss()}>
            {ossSaving ? "保存中…" : "保存配置"}
          </button>
        </div>
      </div>
      <label className="mt-4 flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={ossForm.is_enabled} onChange={(e) => setOssForm((f) => ({ ...f, is_enabled: e.target.checked }))} />
        启用租户自有对象存储
      </label>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-ink-muted">Endpoint（host:port）</span>
          <input
            className="input-field mt-1 w-full"
            placeholder="oss-cn-hangzhou.aliyuncs.com"
            value={ossForm.endpoint}
            onChange={(e) => setOssForm((f) => ({ ...f, endpoint: e.target.value }))}
          />
        </label>
        <label className="block text-sm">
          <span className="text-ink-muted">Bucket</span>
          <input className="input-field mt-1 w-full" value={ossForm.bucket} onChange={(e) => setOssForm((f) => ({ ...f, bucket: e.target.value }))} />
        </label>
        <label className="block text-sm">
          <span className="text-ink-muted">Access Key</span>
          <input className="input-field mt-1 w-full" value={ossForm.access_key} onChange={(e) => setOssForm((f) => ({ ...f, access_key: e.target.value }))} />
        </label>
        <label className="block text-sm">
          <span className="text-ink-muted">Secret Key{oss?.secret_key_masked ? `（已保存 ${oss.secret_key_masked}）` : ""}</span>
          <input
            className="input-field mt-1 w-full"
            type="password"
            placeholder="留空表示不修改"
            value={ossForm.secret_key}
            onChange={(e) => setOssForm((f) => ({ ...f, secret_key: e.target.value }))}
          />
        </label>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={ossForm.secure} onChange={(e) => setOssForm((f) => ({ ...f, secure: e.target.checked }))} />
          使用 HTTPS
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="text-ink-muted">Region（可选）</span>
          <input
            className="input-field mt-1 w-full"
            placeholder="cn-hangzhou"
            value={ossForm.region}
            onChange={(e) => setOssForm((f) => ({ ...f, region: e.target.value }))}
          />
        </label>
      </div>
    </section>
  );
}

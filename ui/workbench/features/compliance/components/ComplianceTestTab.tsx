"use client";

import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { CompliancePageVm } from "@/features/compliance/hooks/use-compliance-page";

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

export function ComplianceTestTab({ vm }: { vm: CompliancePageVm }) {
  const { layoutShell, testText, setTestText, scanBusy, scanResult, onScan, actionLabel } = vm;

  return (
    <ResourceListLayout
      {...layoutShell}
      search=""
      onSearchChange={() => {}}
      showSearch={false}
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

"use client";

import { ScanStatusBadge } from "@/components/compliance/ScanStatusBadge";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import type { CompliancePageVm } from "@/hooks/use-compliance-page";
import { COMPLIANCE_MAIN_TABS, COMPLIANCE_PAGE_DESC } from "@/lib/compliance-page-shared";

export function ComplianceTestTab({ vm }: { vm: CompliancePageVm }) {
  const { tab, setTab, testText, setTestText, scanBusy, scanResult, onScan, actionLabel } = vm;

  return (
    <ResourceListLayout
      title="合规与安全"
      description={COMPLIANCE_PAGE_DESC}
      search=""
      onSearchChange={() => {}}
      showSearch={false}
      tabs={COMPLIANCE_MAIN_TABS}
      activeTab={tab}
      onTabChange={(k) => setTab(k as typeof tab)}
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

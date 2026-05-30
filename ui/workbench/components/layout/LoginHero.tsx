/** 登录页左侧品牌区（链路 §1，无 API）。 */

import { CompanyLogo } from "@/components/brand/company-logo";

export function LoginHero() {
  return (
    <aside className="relative hidden min-h-screen w-[46%] min-w-[320px] overflow-hidden bg-gradient-to-br from-brand-light via-white to-surface-muted lg:flex lg:flex-col lg:justify-between">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute -left-16 top-24 h-56 w-56 rounded-full bg-brand-soft/60 blur-sm" />
        <div className="absolute right-8 top-12 h-32 w-32 rotate-12 rounded-2xl border border-brand/10 bg-white/80 shadow-panel" />
        <div className="absolute bottom-32 left-1/4 h-40 w-40 -rotate-6 rounded-full border-2 border-dashed border-brand/20" />
        <svg className="absolute bottom-0 right-0 h-64 w-64 text-brand/10" viewBox="0 0 200 200" fill="currentColor">
          <polygon points="100,10 190,190 10,190" />
        </svg>
        <div className="absolute left-[55%] top-[38%] h-3 w-3 rounded-full bg-brand" />
        <div className="absolute left-[42%] top-[52%] h-2 w-2 rounded-full bg-brand-soft" />
        <div className="absolute left-[68%] top-[45%] h-4 w-4 rounded-full border-2 border-brand/30 bg-white" />
      </div>

      <div className="relative z-10 flex flex-1 flex-col justify-center px-10 xl:px-14">
        <CompanyLogo variant="full" size="lg" className="mb-6" />
        <h1 className="text-3xl font-bold leading-tight text-ink xl:text-4xl">
          企业级 AI
          <br />
          <span className="text-brand">智能工作台</span>
        </h1>
        <p className="mt-5 max-w-md text-base leading-relaxed text-ink-muted">编排智能体、连接知识库与流程，在统一平台完成 RAG、合规与运维闭环。</p>
        <ul className="mt-8 space-y-2 text-sm text-ink-muted">
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            多租户隔离 · 可观测任务
          </li>
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            可视化流程编排 · 应用市场一键安装
          </li>
        </ul>
      </div>

      <p className="relative z-10 px-10 pb-8 text-xs text-ink-faint xl:px-14">让 AI 能力可编排、可审计、可落地</p>
    </aside>
  );
}

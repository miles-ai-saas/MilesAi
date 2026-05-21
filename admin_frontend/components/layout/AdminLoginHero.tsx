export function AdminLoginHero() {
  return (
    <aside className="relative hidden min-h-screen w-[46%] min-w-[320px] overflow-hidden bg-gradient-to-br from-brand-light via-white to-surface-muted lg:flex lg:flex-col lg:justify-between">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute -left-12 top-20 h-52 w-52 rounded-full bg-brand-soft/70 blur-sm" />
        <div className="absolute right-10 top-16 h-28 w-28 rotate-12 rounded-2xl border border-brand/10 bg-white/90 shadow-panel" />
        <div className="absolute bottom-28 left-[18%] h-36 w-36 -rotate-12 rounded-full border-2 border-dashed border-brand/25" />
        <div className="absolute right-[22%] top-[42%] h-24 w-24 rotate-45 rounded-lg border border-brand/15 bg-brand-light/80" />
        <svg
          className="absolute -bottom-8 -right-4 h-72 w-72 text-brand/10"
          viewBox="0 0 200 200"
          fill="currentColor"
        >
          <polygon points="100,10 190,190 10,190" />
        </svg>
        <div className="absolute left-[48%] top-[36%] h-3 w-3 rounded-full bg-brand" />
        <div className="absolute left-[62%] top-[48%] h-2 w-2 rounded-full bg-brand-soft" />
        <div className="absolute left-[38%] top-[55%] h-4 w-4 rounded-full border-2 border-brand/30 bg-white" />
        <div className="absolute right-[35%] top-[28%] h-16 w-1 rotate-12 rounded-full bg-brand/20" />
      </div>

      <div className="relative z-10 flex flex-1 flex-col justify-center px-10 xl:px-14">
        <p className="mb-3 text-sm font-medium tracking-wide text-brand">AiEngine · 运营</p>
        <h1 className="text-3xl font-bold leading-tight text-ink xl:text-4xl">
          平台级
          <br />
          <span className="text-brand">运营治理中心</span>
        </h1>
        <p className="mt-5 max-w-md text-base leading-relaxed text-ink-muted">
          统一管理租户生命周期、计费套餐、风控策略与审计轨迹，让多租户 AI 平台可管、可控、可追责。
        </p>
        <ul className="mt-8 space-y-2 text-sm text-ink-muted">
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            租户开通 · 配额 · 套餐分配
          </li>
          <li className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            账单生成 · 风险处置 · 全链路审计
          </li>
        </ul>
      </div>

      <p className="relative z-10 px-10 pb-8 text-xs text-ink-faint xl:px-14">
        让平台运营有数据、有边界、有留痕
      </p>
    </aside>
  );
}

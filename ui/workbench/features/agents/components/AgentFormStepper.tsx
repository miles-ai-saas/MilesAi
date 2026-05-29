"use client";

/** 智能体表单步骤条（链路 §3 弹窗）。 */
import { AGENT_FORM_STEPS } from "@/features/agents/lib/agent-form-types";

type Props = {
  step: number;
  onStepClick: (index: number) => void;
  /** 设计模式：步骤下方展示副标题 */
  designMode?: boolean;
};

export function AgentFormStepper({ step, onStepClick, designMode }: Props) {
  const circle = designMode ? "h-7 w-7 text-[11px]" : "h-8 w-8 text-xs";
  const connectorMt = designMode ? "mt-3.5" : "mt-4";

  return (
    <nav className={designMode ? "mb-5" : "mb-8"} aria-label="配置步骤">
      <div className="flex items-start">
        {AGENT_FORM_STEPS.map((s, i) => {
          const done = i < step;
          const active = i === step;
          const lineDone = i < step;
          return (
            <div key={s.title} className="flex min-w-0 flex-1 items-start">
              <button type="button" onClick={() => onStepClick(i)} className="group flex min-w-0 flex-1 flex-col items-center px-0.5">
                <span
                  className={`relative z-10 flex shrink-0 items-center justify-center rounded-full font-medium transition ${circle} ${
                    active
                      ? "bg-brand text-brand-foreground ring-2 ring-brand/20"
                      : done
                        ? "bg-brand/10 text-brand"
                        : "border border-line bg-surface text-ink-faint group-hover:border-brand/40 group-hover:text-ink-muted"
                  }`}
                >
                  {done ? (
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  className={`mt-1.5 text-center leading-tight ${
                    designMode ? "text-[10px]" : "text-[11px]"
                  } ${active ? "font-medium text-brand" : "text-ink-muted"}`}
                >
                  {s.title}
                </span>
              </button>
              {i < AGENT_FORM_STEPS.length - 1 && (
                <div className={`mx-0.5 hidden h-px min-w-[8px] flex-1 sm:block ${connectorMt} ${lineDone ? "bg-brand/30" : "bg-line"}`} aria-hidden />
              )}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

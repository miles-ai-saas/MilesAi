"use client";

/** 对话页右侧配置侧栏（链路 §5 + §4 agent meta）。 */
import type { ReactNode } from "react";
import { AGENT_WORKBENCH_TABS, type AgentWorkbenchTab } from "@/features/agents/components/agent-workbench-tabs";
import { CHAT_RIGHT_RAIL_COLLAPSED, CHAT_RIGHT_RAIL_EXPANDED } from "@/features/agents/components/chat-sidebar-layout";
import { AgentRenameInline } from "@/features/agents/components/AgentRenameInline";
import { SidebarCollapseButton } from "@/features/agents/components/SidebarCollapseButton";
import { agentModeLabel, agentStatusLabel } from "@/features/agents/lib/agent-utils";
import { useAgentMeta } from "@/features/agents/hooks/use-agent-meta";
import type { Agent } from "@/lib/types";

const workbenchTabIconPaths: Record<AgentWorkbenchTab, ReactNode> = {
  config: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M10.3 4.2h3.4M12 3v2.4M6.8 8.2l1.7-1M6.8 15.8l1.7 1M17.2 8.2l-1.7-1M17.2 15.8l-1.7 1M4.2 10.3v3.4M3 12h2.4M19.8 10.3v3.4M21 12h-2.4M8.2 12a3.8 3.8 0 107.6 0 3.8 3.8 0 00-7.6 0z"
    />
  ),
  trace: <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h10M4 14h14M4 18h8M17 16l2 2 4-4" />,
  schedule: <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
  architecture: <path strokeLinecap="round" strokeLinejoin="round" d="M5 7h4v4H5V7zm10 0h4v4h-4V7zM5 17h4v4H5v-4zm10 0h4v4h-4v-4z" />,
  api: <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l-2 2 2 2M16 9l2 2-2 2M14 7l-4 10" />,
  call_records: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h10M7 16h6M6 5h12a2 2 0 012 2v10a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2z" />
  ),
  stats: <path strokeLinecap="round" strokeLinejoin="round" d="M6 17V11M12 17V7M18 17v-4" />,
};

function WorkbenchTabIcon({ tab, className = "h-4 w-4" }: { tab: AgentWorkbenchTab; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      {workbenchTabIconPaths[tab]}
    </svg>
  );
}

type Props = {
  agent: Agent | null;
  activeTab: AgentWorkbenchTab;
  panelOpen: boolean;
  collapsed: boolean;
  hideCollapseButton?: boolean;
  onToggleCollapse: () => void;
  onTabChange: (tab: AgentWorkbenchTab) => void;
  onAgentRenamed?: (name: string) => void;
};

export function AgentWorkbenchSidebar({ agent, activeTab, panelOpen, collapsed, hideCollapseButton, onToggleCollapse, onTabChange, onAgentRenamed }: Props) {
  const agentMeta = useAgentMeta(Boolean(agent));

  return (
    <aside
      className="relative z-30 flex h-full shrink-0 flex-col overflow-hidden border-l border-line bg-surface transition-[width] duration-200 ease-out"
      style={{ width: collapsed ? CHAT_RIGHT_RAIL_COLLAPSED : CHAT_RIGHT_RAIL_EXPANDED }}
    >
      <SidebarCollapseButton side="right" collapsed={collapsed} onToggle={onToggleCollapse} hidden={hideCollapseButton} />

      {collapsed ? (
        <nav className="flex flex-1 flex-col items-center gap-1 overflow-y-auto py-3" aria-label="工作台">
          {AGENT_WORKBENCH_TABS.map((item) => {
            const active = panelOpen && activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                disabled={!agent}
                title={!agent ? "请先选择智能体" : !item.ready ? `${item.label}（开发中）` : item.label}
                onClick={() => onTabChange(item.id)}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                  active ? "bg-brand-light text-brand" : agent ? "text-ink-muted hover:bg-brand-light/50 hover:text-brand" : "cursor-not-allowed opacity-40"
                }`}
              >
                <WorkbenchTabIcon tab={item.id} className="h-5 w-5" />
              </button>
            );
          })}
        </nav>
      ) : (
        <>
          {agent ? (
            <div className="border-b border-line-soft px-4 py-4">
              <AgentRenameInline agentId={agent.id} name={agent.name} prominent className="text-sm leading-snug" onRenamed={(name) => onAgentRenamed?.(name)} />
              <p className="mt-1.5 text-xs text-ink-muted">{agentModeLabel(agent)}</p>
              <span
                className={`mt-2 inline-block rounded-md px-2 py-0.5 text-xs ${
                  agent.status === "enabled" ? "bg-brand-light text-brand" : "border border-line text-ink-faint"
                }`}
              >
                {agentStatusLabel(agent.status, agentMeta)}
              </span>
            </div>
          ) : (
            <div className="border-b border-line-soft px-4 py-5 text-xs text-ink-faint">未选择智能体</div>
          )}

          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3" aria-label="工作台">
            {AGENT_WORKBENCH_TABS.map((item) => {
              const active = panelOpen && activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  disabled={!agent}
                  title={!item.ready ? `${item.label}（开发中）` : item.label}
                  onClick={() => onTabChange(item.id)}
                  className={`workbench-rail-item ${
                    active ? "workbench-rail-item-active" : agent ? "workbench-rail-item-idle" : "cursor-not-allowed opacity-40"
                  }`}
                >
                  {active && <span className="absolute bottom-3 left-0 top-3 w-1 rounded-r bg-brand" aria-hidden />}
                  <WorkbenchTabIcon tab={item.id} className={`h-5 w-5 shrink-0 ${active ? "text-brand" : "text-ink-muted"}`} />
                  <span className="min-w-0 flex-1 font-medium leading-snug">{item.label}</span>
                  {!item.ready && <span className="shrink-0 rounded border border-line px-1 py-px text-[10px] leading-none text-ink-faint">待开</span>}
                </button>
              );
            })}
          </nav>
        </>
      )}
    </aside>
  );
}

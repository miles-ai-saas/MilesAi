"use client";

import {
  AGENT_WORKBENCH_TABS,
  type AgentWorkbenchTab,
} from "@/components/agent/agent-workbench-tabs";
import {
  CHAT_RIGHT_RAIL_COLLAPSED,
  CHAT_RIGHT_RAIL_EXPANDED,
} from "@/components/agent/chat-sidebar-layout";
import { SidebarCollapseButton } from "@/components/agent/SidebarCollapseButton";
import { WorkbenchTabIcon } from "@/components/agent/WorkbenchTabIcon";
import { agentModeLabel, agentStatusLabel } from "@/lib/agent-utils";
import type { Agent } from "@/lib/types";

type Props = {
  agent: Agent | null;
  activeTab: AgentWorkbenchTab;
  panelOpen: boolean;
  collapsed: boolean;
  hideCollapseButton?: boolean;
  onToggleCollapse: () => void;
  onTabChange: (tab: AgentWorkbenchTab) => void;
};

export function AgentWorkbenchSidebar({
  agent,
  activeTab,
  panelOpen,
  collapsed,
  hideCollapseButton,
  onToggleCollapse,
  onTabChange,
}: Props) {
  return (
    <aside
      className="relative z-30 flex h-full shrink-0 flex-col overflow-hidden border-l border-line bg-surface transition-[width] duration-200 ease-out"
      style={{ width: collapsed ? CHAT_RIGHT_RAIL_COLLAPSED : CHAT_RIGHT_RAIL_EXPANDED }}
    >
      <SidebarCollapseButton
        side="right"
        collapsed={collapsed}
        onToggle={onToggleCollapse}
        hidden={hideCollapseButton}
      />

      {collapsed ? (
        <nav className="flex flex-1 flex-col items-center gap-1 overflow-y-auto py-3" aria-label="工作台">
          {AGENT_WORKBENCH_TABS.map((item) => {
            const active = panelOpen && activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                disabled={!agent}
                title={
                  !agent
                    ? "请先选择智能体"
                    : !item.ready
                      ? `${item.label}（开发中）`
                      : item.label
                }
                onClick={() => onTabChange(item.id)}
                className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                  active
                    ? "bg-brand-light text-brand"
                    : agent
                      ? "text-ink-muted hover:bg-brand-light/50 hover:text-brand"
                      : "cursor-not-allowed opacity-40"
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
              <p className="line-clamp-2 text-sm font-medium leading-snug text-ink" title={agent.name}>
                {agent.name}
              </p>
              <p className="mt-1.5 text-xs text-ink-muted">{agentModeLabel(agent)}</p>
              <span
                className={`mt-2 inline-block rounded-md px-2 py-0.5 text-xs ${
                  agent.status === "enabled"
                    ? "bg-brand-light text-brand"
                    : "border border-line text-ink-faint"
                }`}
              >
                {agentStatusLabel(agent.status)}
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
                    active
                      ? "workbench-rail-item-active"
                      : agent
                        ? "workbench-rail-item-idle"
                        : "cursor-not-allowed opacity-40"
                  }`}
                >
                  {active && (
                    <span
                      className="absolute bottom-3 left-0 top-3 w-1 rounded-r bg-brand"
                      aria-hidden
                    />
                  )}
                  <WorkbenchTabIcon
                    tab={item.id}
                    className={`h-5 w-5 shrink-0 ${active ? "text-brand" : "text-ink-muted"}`}
                  />
                  <span className="min-w-0 flex-1 font-medium leading-snug">{item.label}</span>
                  {!item.ready && (
                    <span className="shrink-0 rounded border border-line px-1 py-px text-[10px] leading-none text-ink-faint">
                      待开
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </>
      )}
    </aside>
  );
}

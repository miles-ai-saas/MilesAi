"use client";

import type { ReactNode } from "react";
import type { AgentWorkbenchTab } from "@/components/agent/agent-workbench-tabs";

const paths: Record<AgentWorkbenchTab, ReactNode> = {
  config: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M10.3 4.2h3.4M12 3v2.4M6.8 8.2l1.7-1M6.8 15.8l1.7 1M17.2 8.2l-1.7-1M17.2 15.8l-1.7 1M4.2 10.3v3.4M3 12h2.4M19.8 10.3v3.4M21 12h-2.4M8.2 12a3.8 3.8 0 107.6 0 3.8 3.8 0 00-7.6 0z"
    />
  ),
  trace: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M4 6h16M4 10h10M4 14h14M4 18h8M17 16l2 2 4-4"
    />
  ),
  schedule: (
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  ),
  architecture: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M5 7h4v4H5V7zm10 0h4v4h-4V7zM5 17h4v4H5v-4zm10 0h4v4h-4v-4z"
    />
  ),
  api: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M8 9l-2 2 2 2M16 9l2 2-2 2M14 7l-4 10"
    />
  ),
  logs: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M7 8h10M7 12h10M7 16h6M6 5h12a2 2 0 012 2v10a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2z"
    />
  ),
  stats: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M6 17V11M12 17V7M18 17v-4"
    />
  ),
};

type Props = {
  tab: AgentWorkbenchTab;
  className?: string;
};

export function WorkbenchTabIcon({ tab, className = "h-4 w-4" }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      aria-hidden
    >
      {paths[tab]}
    </svg>
  );
}

import type { BizContract, BizOpportunity, BizProject } from "@/lib/types";

export type ClientTimelineItem = {
  id: string;
  kind: "project" | "opportunity" | "contract";
  title: string;
  status: string;
  date: string;
  href: string;
};

export function buildClientTimeline(
  projects: BizProject[],
  opportunities: BizOpportunity[],
  contracts: BizContract[],
): ClientTimelineItem[] {
  const items: ClientTimelineItem[] = [
    ...projects.map((p) => ({
      id: p.id,
      kind: "project" as const,
      title: p.name,
      status: p.status,
      date: "",
      href: `/business/projects/${p.id}`,
    })),
    ...opportunities.map((o) => ({
      id: o.id,
      kind: "opportunity" as const,
      title: o.name,
      status: o.stage,
      date: o.expected_close_date ?? "",
      href: `/business/opportunities/${o.id}`,
    })),
    ...contracts.map((c) => ({
      id: c.id,
      kind: "contract" as const,
      title: c.name,
      status: c.status,
      date: c.signed_date ?? "",
      href: `/business/contracts/${c.id}`,
    })),
  ];
  return items.sort((a, b) => (b.date || "9999").localeCompare(a.date || "9999"));
}

export const TIMELINE_KIND_LABELS: Record<ClientTimelineItem["kind"], string> = {
  project: "项目",
  opportunity: "商机",
  contract: "合同",
};

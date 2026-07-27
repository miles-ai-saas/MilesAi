"use client";

/** 智能体表单资源加载 hook — 消除 FormDialog / WorkbenchPanel / DetailDialog 的重复请求。 */

import { Dispatch, SetStateAction, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Agent, A2aPeer, Flow, KnowledgeBase, McpService, ModelConfig, PromptTemplate, SkillPackage, SysCategory, ToolCatalogItem } from "@/lib/types";

type ResourceOptions = {
  /** 是否加载 Agent 详情（edit/工作台场景） */
  loadAgent?: string;
  /** 是否加载工具目录 */
  loadToolCatalog?: boolean;
  /** 是否加载同行列表（Agent/分类/Peers） */
  loadPeers?: boolean;
};

type ResourceData = {
  kbs: KnowledgeBase[];
  flows: Flow[];
  prompts: PromptTemplate[];
  models: ModelConfig[];
  skills: SkillPackage[];
  mcps: McpService[];
  toolCatalog: ToolCatalogItem[];
  allAgents: Agent[];
  a2aPeers: A2aPeer[];
  categories: SysCategory[];
  agent: Agent | null;
  setAgent: Dispatch<SetStateAction<Agent | null>>;
  loading: boolean;
};

/** 模块级简单缓存，同一 session 内无需重复请求。 */
let cached: {
  kbs?: KnowledgeBase[];
  flows?: Flow[];
  prompts?: PromptTemplate[];
  models?: ModelConfig[];
  skills?: SkillPackage[];
  mcps?: McpService[];
  toolCatalog?: ToolCatalogItem[];
  agents?: Agent[];
  a2aPeers?: A2aPeer[];
  categories?: SysCategory[];
} = {};

export function clearAgentResourceCache(): void {
  cached = {};
}

function isAgentDetail(value: unknown): value is Agent {
  return Boolean(value && typeof value === "object" && "id" in value && "name" in value && !("items" in value));
}

export function useAgentFormResources(when: boolean, opts: ResourceOptions = {}): ResourceData {
  const { loadAgent, loadToolCatalog = false, loadPeers = false } = opts;

  const [kbs, setKbs] = useState<KnowledgeBase[]>(cached.kbs ?? []);
  const [flows, setFlows] = useState<Flow[]>(cached.flows ?? []);
  const [prompts, setPrompts] = useState<PromptTemplate[]>(cached.prompts ?? []);
  const [models, setModels] = useState<ModelConfig[]>(cached.models ?? []);
  const [skills, setSkills] = useState<SkillPackage[]>(cached.skills ?? []);
  const [mcps, setMcps] = useState<McpService[]>(cached.mcps ?? []);
  const [toolCatalog, setToolCatalog] = useState<ToolCatalogItem[]>(cached.toolCatalog ?? []);
  const [allAgents, setAllAgents] = useState<Agent[]>(cached.agents ?? []);
  const [a2aPeers, setA2aPeers] = useState<A2aPeer[]>(cached.a2aPeers ?? []);
  const [categories, setCategories] = useState<SysCategory[]>(cached.categories ?? []);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!when) return;

    // 切换智能体时先清空，避免旧详情短暂写入表单
    setAgent(null);

    const baseHits =
      cached.kbs != null && cached.flows != null && cached.prompts != null && cached.models != null && cached.skills != null && cached.mcps != null;
    const toolHit = !loadToolCatalog || cached.toolCatalog != null;
    const peerHit = !loadPeers || (cached.agents != null && cached.a2aPeers != null && cached.categories != null);

    if (baseHits && toolHit && peerHit && !loadAgent) return;

    setLoading(true);

    type Slot =
      | { kind: "kb" }
      | { kind: "flow" }
      | { kind: "prompt" }
      | { kind: "model" }
      | { kind: "skill" }
      | { kind: "mcp" }
      | { kind: "toolCatalog" }
      | { kind: "agents" }
      | { kind: "a2aPeers" }
      | { kind: "categories" }
      | { kind: "agent" };

    const slots: Slot[] = [];
    const requests: Promise<unknown>[] = [];

    const pushCachedOrFetch = (kind: Slot["kind"], hit: boolean, fetch: () => Promise<unknown>) => {
      slots.push({ kind } as Slot);
      requests.push(hit ? Promise.resolve(null) : fetch());
    };

    pushCachedOrFetch("kb", cached.kbs != null, () => api.listKbs(1, 100));
    pushCachedOrFetch("flow", cached.flows != null, () => api.listFlows(1, 100));
    pushCachedOrFetch("prompt", cached.prompts != null, () => api.listPromptTemplates(1, 100));
    pushCachedOrFetch("model", cached.models != null, () => api.listModelConfigs());
    pushCachedOrFetch("skill", cached.skills != null, () => api.listSkillPackages(1, 100));
    pushCachedOrFetch("mcp", cached.mcps != null, () => api.listMcpServices(1, 100));

    if (loadToolCatalog) pushCachedOrFetch("toolCatalog", cached.toolCatalog != null, () => api.listToolCatalog());
    if (loadPeers) {
      pushCachedOrFetch("agents", cached.agents != null, () => api.listAgents(1, 100));
      pushCachedOrFetch("a2aPeers", cached.a2aPeers != null, () => api.listA2aPeers(1, 100));
      pushCachedOrFetch("categories", cached.categories != null, () => api.listCategories("agent"));
    }
    if (loadAgent) {
      slots.push({ kind: "agent" });
      requests.push(api.getAgent(loadAgent));
    }

    let cancelled = false;
    void Promise.all(requests)
      .then((results) => {
        if (cancelled) return;
        results.forEach((result, idx) => {
          const kind = slots[idx]?.kind;
          if (!kind || result == null) return;
          switch (kind) {
            case "kb":
              if (!cached.kbs) {
                cached.kbs = (result as { items: KnowledgeBase[] }).items;
                setKbs(cached.kbs);
              }
              break;
            case "flow":
              if (!cached.flows) {
                cached.flows = (result as { items: Flow[] }).items.filter((f) => f.status === "published");
                setFlows(cached.flows);
              }
              break;
            case "prompt":
              if (!cached.prompts) {
                cached.prompts = (result as { items: PromptTemplate[] }).items;
                setPrompts(cached.prompts);
              }
              break;
            case "model":
              if (!cached.models) {
                cached.models = result as ModelConfig[];
                setModels(cached.models);
              }
              break;
            case "skill":
              if (!cached.skills) {
                cached.skills = (result as { items: SkillPackage[] }).items.filter((s) => s.is_active);
                setSkills(cached.skills);
              }
              break;
            case "mcp":
              if (!cached.mcps) {
                cached.mcps = (result as { items: McpService[] }).items;
                setMcps(cached.mcps);
              }
              break;
            case "toolCatalog":
              if (!cached.toolCatalog) {
                cached.toolCatalog = result as ToolCatalogItem[];
                setToolCatalog(cached.toolCatalog);
              }
              break;
            case "agents":
              if (!cached.agents) {
                cached.agents = (result as { items: Agent[] }).items;
                setAllAgents(cached.agents);
              }
              break;
            case "a2aPeers":
              if (!cached.a2aPeers) {
                cached.a2aPeers = (result as { items: A2aPeer[] }).items.filter((p) => p.status === "active");
                setA2aPeers(cached.a2aPeers);
              }
              break;
            case "categories":
              if (!cached.categories) {
                cached.categories = result as SysCategory[];
                setCategories(cached.categories);
              }
              break;
            case "agent":
              if (isAgentDetail(result) && (!loadAgent || result.id === loadAgent)) {
                setAgent(result);
              }
              break;
          }
        });
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [when, loadAgent, loadToolCatalog, loadPeers]);

  return { kbs, flows, prompts, models, skills, mcps, toolCatalog, allAgents, a2aPeers, categories, agent, setAgent, loading };
}

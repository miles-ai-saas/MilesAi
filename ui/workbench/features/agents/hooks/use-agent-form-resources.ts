"use client";

/** 智能体表单资源加载 hook — 消除 FormDialog / WorkbenchPanel / DetailDialog 的重复请求。 */

import { useEffect, useState } from "react";
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

    const baseHits =
      cached.kbs != null && cached.flows != null && cached.prompts != null && cached.models != null && cached.skills != null && cached.mcps != null;
    const toolHit = !loadToolCatalog || cached.toolCatalog != null;
    const peerHit = !loadPeers || (cached.agents != null && cached.a2aPeers != null && cached.categories != null);

    if (baseHits && toolHit && peerHit && !loadAgent) return;

    setLoading(true);
    const baseRequests: Promise<unknown>[] = [];
    baseRequests.push(...(cached.kbs == null ? [api.listKbs(1, 100)] : [Promise.resolve(null)]));
    baseRequests.push(...(cached.flows == null ? [api.listFlows(1, 100)] : [Promise.resolve(null)]));
    baseRequests.push(...(cached.prompts == null ? [api.listPromptTemplates(1, 100)] : [Promise.resolve(null)]));
    baseRequests.push(...(cached.models == null ? [api.listModelConfigs()] : [Promise.resolve(null)]));
    baseRequests.push(...(cached.skills == null ? [api.listSkillPackages(1, 100)] : [Promise.resolve(null)]));
    baseRequests.push(...(cached.mcps == null ? [api.listMcpServices(1, 100)] : [Promise.resolve(null)]));

    if (loadToolCatalog && cached.toolCatalog == null) baseRequests.push(api.listToolCatalog());
    if (loadPeers && cached.agents == null) baseRequests.push(api.listAgents(1, 100));
    if (loadPeers && cached.a2aPeers == null) baseRequests.push(api.listA2aPeers(1, 100));
    if (loadPeers && cached.categories == null) baseRequests.push(api.listCategories("agent"));
    // agent 不缓存，每次 agentId 变化都重新获取
    if (loadAgent) baseRequests.push(api.getAgent(loadAgent));

    void Promise.all(baseRequests).then((results) => {
      let i = 0;
      const maybeKb = results[i++];
      const maybeFlow = results[i++];
      const maybePrompt = results[i++];
      const maybeModel = results[i++];
      const maybeSkill = results[i++];
      const maybeMcp = results[i++];

      if (maybeKb && !cached.kbs) { cached.kbs = (maybeKb as { items: KnowledgeBase[] }).items; setKbs(cached.kbs); }
      if (maybeFlow && !cached.flows) { cached.flows = (maybeFlow as { items: Flow[] }).items.filter((f) => f.status === "published"); setFlows(cached.flows); }
      if (maybePrompt && !cached.prompts) { cached.prompts = (maybePrompt as { items: PromptTemplate[] }).items; setPrompts(cached.prompts); }
      if (maybeModel && !cached.models) { cached.models = maybeModel as ModelConfig[]; setModels(cached.models); }
      if (maybeSkill && !cached.skills) { cached.skills = (maybeSkill as { items: SkillPackage[] }).items.filter((s) => s.is_active); setSkills(cached.skills); }
      if (maybeMcp && !cached.mcps) { cached.mcps = (maybeMcp as { items: McpService[] }).items; setMcps(cached.mcps); }

      if (loadToolCatalog && results[i] && !cached.toolCatalog) { cached.toolCatalog = results[i] as ToolCatalogItem[]; setToolCatalog(cached.toolCatalog); i++; }
      if (loadPeers && results[i] && !cached.agents) { cached.agents = (results[i] as { items: Agent[] }).items; setAllAgents(cached.agents); i++; }
      if (loadPeers && results[i] && !cached.a2aPeers) { cached.a2aPeers = (results[i] as { items: A2aPeer[] }).items.filter((p) => p.status === "active"); setA2aPeers(cached.a2aPeers); i++; }
      if (loadPeers && results[i] && !cached.categories) { cached.categories = results[i] as SysCategory[]; setCategories(cached.categories); i++; }
      if (loadAgent && results[i] != null) setAgent(results[i] as Agent);

      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, [when, loadAgent, loadToolCatalog, loadPeers]);

  return { kbs, flows, prompts, models, skills, mcps, toolCatalog, allAgents, a2aPeers, categories, agent, loading };
}

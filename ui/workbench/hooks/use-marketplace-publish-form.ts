"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MarketplaceMainView } from "@/lib/marketplace-page-shared";
import type { Agent, Flow, KnowledgeBase } from "@/lib/types";

type Params = {
  ready: boolean;
  mainView: MarketplaceMainView;
  setMsg: (msg: string) => void;
  switchView: (view: MarketplaceMainView) => void;
  reloadMyApps: () => Promise<void>;
};

export function useMarketplacePublishForm({ ready, mainView, setMsg, switchView, reloadMyApps }: Params) {
  const [publishName, setPublishName] = useState("");
  const [publishDesc, setPublishDesc] = useState("");
  const [publishIcon, setPublishIcon] = useState("📦");
  const [publishCategory, setPublishCategory] = useState("rag");
  const [publishKbId, setPublishKbId] = useState("");
  const [publishFlowId, setPublishFlowId] = useState("");
  const [publishAgentId, setPublishAgentId] = useState("");
  const [publishTagIds, setPublishTagIds] = useState<string[]>([]);
  const [publishVisibility, setPublishVisibility] = useState<"public" | "tenant_only">("public");
  const [publishLoading, setPublishLoading] = useState(false);
  const [resourceOptions, setResourceOptions] = useState<{
    kbs: KnowledgeBase[];
    flows: Flow[];
    agents: Agent[];
  }>({ kbs: [], flows: [], agents: [] });

  useEffect(() => {
    if (!ready || mainView !== "publish") return;
    Promise.all([api.listKbs(1, 100), api.listFlows(1, 100), api.listAgents(1, 100)]).then(([kbRes, flowRes, agentRes]) => {
      setResourceOptions({
        kbs: kbRes.items,
        flows: flowRes.items,
        agents: agentRes.items,
      });
    });
  }, [ready, mainView]);

  const onCreateDraft = async () => {
    if (!publishName.trim()) {
      setMsg("请填写应用名称");
      return;
    }
    if (!publishKbId && !publishFlowId && !publishAgentId) {
      setMsg("请至少选择知识库、流程或智能体之一");
      return;
    }
    setPublishLoading(true);
    setMsg("");
    try {
      await api.createMarketplaceAppFromResources({
        name: publishName.trim(),
        description: publishDesc.trim() || undefined,
        icon: publishIcon || "📦",
        category_slug: publishCategory || undefined,
        kb_id: publishKbId || undefined,
        flow_id: publishFlowId || undefined,
        agent_id: publishAgentId || undefined,
        tag_ids: publishTagIds,
        visibility: publishVisibility,
      });
      setMsg("草稿已创建，可在「我的上架」中提交审核");
      setPublishName("");
      setPublishDesc("");
      setPublishKbId("");
      setPublishFlowId("");
      setPublishAgentId("");
      setPublishTagIds([]);
      switchView("mine");
      await reloadMyApps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setPublishLoading(false);
    }
  };

  return {
    publishName,
    setPublishName,
    publishDesc,
    setPublishDesc,
    publishIcon,
    setPublishIcon,
    publishCategory,
    setPublishCategory,
    publishKbId,
    setPublishKbId,
    publishFlowId,
    setPublishFlowId,
    publishAgentId,
    setPublishAgentId,
    publishTagIds,
    setPublishTagIds,
    publishVisibility,
    setPublishVisibility,
    publishLoading,
    resourceOptions,
    onCreateDraft,
  };
}

export type MarketplacePublishForm = ReturnType<typeof useMarketplacePublishForm>;

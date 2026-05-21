"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import type {
  Agent,
  Flow,
  KnowledgeBase,
  McpService,
  ModelConfig,
  PromptTemplate,
  SkillPackage,
} from "@/lib/types";

export type AgentFormValues = {
  name: string;
  description: string;
  system_prompt: string;
  kb_ids: string[];
  published_flow_id: string;
  prompt_template_id: string;
  model_config_id: string;
  skill_package_id: string;
  mcp_service_ids: string[];
};

const emptyForm = (): AgentFormValues => ({
  name: "",
  description: "",
  system_prompt: "",
  kb_ids: [],
  published_flow_id: "",
  prompt_template_id: "",
  model_config_id: "",
  skill_package_id: "",
  mcp_service_ids: [],
});

type Props = {
  open: boolean;
  title: string;
  agent?: Agent | null;
  onClose: () => void;
  onSaved: () => void;
};

export function AgentFormDialog({ open, title, agent, onClose, onSaved }: Props) {
  const [form, setForm] = useState<AgentFormValues>(emptyForm);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [mcps, setMcps] = useState<McpService[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    Promise.all([
      api.listKbs(1, 100),
      api.listFlows(1, 100),
      api.listPromptTemplates(1, 100),
      api.listModelConfigs(),
      api.listSkillPackages(1, 100),
      api.listMcpServices(1, 100),
    ]).then(([kbRes, flowRes, promptRes, modelRes, skillRes, mcpRes]) => {
      setKbs(kbRes.items);
      setFlows(flowRes.items.filter((f) => f.status === "published"));
      setPrompts(promptRes.items);
      setModels(modelRes);
      setSkills(skillRes.items.filter((s) => s.is_active));
      setMcps(mcpRes.items);
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (agent) {
      setForm({
        name: agent.name,
        description: agent.description ?? "",
        system_prompt: agent.system_prompt ?? "",
        kb_ids: agent.kb_ids ?? [],
        published_flow_id: agent.published_flow_id ?? "",
        prompt_template_id: agent.prompt_template_id ?? "",
        model_config_id: agent.model_config_id ?? "",
        skill_package_id: String((agent.config as Record<string, unknown>)?.skill_package_id ?? ""),
        mcp_service_ids: (
          ((agent.config as Record<string, unknown>)?.mcp_service_ids as string[]) ?? []
        ).map(String),
      });
    } else {
      setForm(emptyForm());
    }
  }, [open, agent]);

  const toggleMcp = (id: string) => {
    setForm((f) => ({
      ...f,
      mcp_service_ids: f.mcp_service_ids.includes(id)
        ? f.mcp_service_ids.filter((x) => x !== id)
        : [...f.mcp_service_ids, id],
    }));
  };

  const toggleKb = (id: string) => {
    setForm((f) => ({
      ...f,
      kb_ids: f.kb_ids.includes(id) ? f.kb_ids.filter((x) => x !== id) : [...f.kb_ids, id],
    }));
  };

  const onSubmit = async () => {
    if (!form.name.trim()) return;
    setBusy(true);
    try {
      const config: Record<string, unknown> = {
        ...((agent?.config as Record<string, unknown>) ?? {}),
      };
      if (form.skill_package_id) config.skill_package_id = form.skill_package_id;
      else delete config.skill_package_id;
      if (form.mcp_service_ids.length) config.mcp_service_ids = form.mcp_service_ids;
      else delete config.mcp_service_ids;

      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        system_prompt: form.system_prompt.trim() || undefined,
        kb_ids: form.kb_ids,
        published_flow_id: form.published_flow_id || null,
        prompt_template_id: form.prompt_template_id || null,
        model_config_id: form.model_config_id || null,
        config,
      };
      if (agent) {
        await api.updateAgent(agent.id, payload);
      } else {
        await api.createAgent({
          ...payload,
          published_flow_id: form.published_flow_id || undefined,
          prompt_template_id: form.prompt_template_id || undefined,
          model_config_id: form.model_config_id || undefined,
        });
      }
      onSaved();
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={onSubmit}>
            {busy ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <input
        className="input-field w-full"
        placeholder="名称"
        value={form.name}
        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
      />
      <input
        className="input-field w-full"
        placeholder="描述（可选）"
        value={form.description}
        onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
      />
      <textarea
        className="input-field h-24 w-full font-mono text-sm"
        placeholder="系统提示词（可选，留空则使用模板）"
        value={form.system_prompt}
        onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
      />
      <select
        className="input-field w-full"
        value={form.model_config_id}
        onChange={(e) => setForm((f) => ({ ...f, model_config_id: e.target.value }))}
      >
        <option value="">默认模型</option>
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} ({m.model_name})
          </option>
        ))}
      </select>
      <select
        className="input-field w-full"
        value={form.prompt_template_id}
        onChange={(e) => setForm((f) => ({ ...f, prompt_template_id: e.target.value }))}
      >
        <option value="">无提示词模板</option>
        {prompts.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <select
        className="input-field w-full"
        value={form.published_flow_id}
        onChange={(e) => setForm((f) => ({ ...f, published_flow_id: e.target.value }))}
      >
        <option value="">无流程（直连/RAG）</option>
        {flows.map((fl) => (
          <option key={fl.id} value={fl.id}>
            {fl.name}
          </option>
        ))}
      </select>
      <select
        className="input-field w-full"
        value={form.skill_package_id}
        onChange={(e) => setForm((f) => ({ ...f, skill_package_id: e.target.value }))}
      >
        <option value="">无技能包</option>
        {skills.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      <div className="rounded border border-line-soft p-3">
        <p className="mb-2 text-xs font-medium text-ink-muted">MCP 服务（可多选，需已同步工具）</p>
        <div className="flex max-h-24 flex-wrap gap-2 overflow-y-auto">
          {mcps.length === 0 && <span className="text-xs text-ink-faint">暂无 MCP 服务</span>}
          {mcps.map((m) => (
            <label key={m.id} className="flex cursor-pointer items-center gap-1 text-xs">
              <input
                type="checkbox"
                checked={form.mcp_service_ids.includes(m.id)}
                onChange={() => toggleMcp(m.id)}
              />
              {m.name} ({m.tools_cache?.length ?? 0})
            </label>
          ))}
        </div>
      </div>
      <div className="rounded border border-line-soft p-3">
        <p className="mb-2 text-xs font-medium text-ink-muted">知识库（可多选，可选）</p>
        <div className="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
          {kbs.length === 0 && <span className="text-xs text-ink-faint">暂无知识库</span>}
          {kbs.map((kb) => (
            <label key={kb.id} className="flex cursor-pointer items-center gap-1 text-xs">
              <input
                type="checkbox"
                checked={form.kb_ids.includes(kb.id)}
                onChange={() => toggleKb(kb.id)}
              />
              {kb.name}
            </label>
          ))}
        </div>
      </div>
    </ResourceDialog>
  );
}

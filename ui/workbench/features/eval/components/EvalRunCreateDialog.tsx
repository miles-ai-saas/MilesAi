"use client";

import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { api } from "@/lib/api";
import { EVAL_SCORING_MODE_OPTIONS } from "@/features/eval/lib/eval-labels";
import type { Agent, EvalDataset, EvalScoringMode, ModelConfig } from "@/lib/types";

type Props = {
  open: boolean;
  datasets: EvalDataset[];
  onClose: () => void;
  onCreate: (payload: {
    dataset_id: string;
    agent_id: string;
    scoring_mode: EvalScoringMode;
    judge_model_config_id?: string | null;
  }) => Promise<unknown>;
};

export function EvalRunCreateDialog({ open, datasets, onClose, onCreate }: Props) {
  const [datasetId, setDatasetId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [scoringMode, setScoringMode] = useState<EvalScoringMode>("auto");
  const [judgeModelId, setJudgeModelId] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setScoringMode("auto");
    setJudgeModelId("");
    setDatasetId(datasets[0]?.id ?? "");
    setAgentId("");
    setAgentsLoading(true);
    void Promise.all([api.listAgents(1, 100), api.listModelConfigs()])
      .then(([page, modelList]) => {
        setAgents(page.items);
        setAgentId(page.items[0]?.id ?? "");
        setModels(Array.isArray(modelList) ? modelList : []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setAgentsLoading(false));
  }, [open, datasets]);

  const canSubmit = !!datasetId && !!agentId;
  const needsJudge = scoringMode === "llm_judge" || scoringMode === "auto";

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError("");
    try {
      await onCreate({
        dataset_id: datasetId,
        agent_id: agentId,
        scoring_mode: scoringMode,
        judge_model_config_id: needsJudge && judgeModelId ? judgeModelId : null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ResourceDialog
      open={open}
      title="新建评测运行"
      description="选择数据集与智能体；创建后可在详情中启动。"
      size="md"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={busy || !canSubmit || agentsLoading}
            onClick={() => void submit()}
          >
            {busy ? "创建中…" : "创建"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">数据集</span>
          <select className="input-field w-full" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {datasets.length === 0 ? <option value="">暂无数据集</option> : null}
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}（{d.case_count} 用例）
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">智能体</span>
          <select
            className="input-field w-full"
            value={agentId}
            disabled={agentsLoading}
            onChange={(e) => setAgentId(e.target.value)}
          >
            {agentsLoading ? <option value="">加载中…</option> : null}
            {!agentsLoading && agents.length === 0 ? <option value="">暂无智能体</option> : null}
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">打分模式</span>
          <select
            className="input-field w-full"
            value={scoringMode}
            onChange={(e) => setScoringMode(e.target.value as EvalScoringMode)}
          >
            {EVAL_SCORING_MODE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        {needsJudge ? (
          <>
            <p className="text-xs text-ink-muted">
              {scoringMode === "llm_judge"
                ? "LLM Judge 会按用例的「评分标准（rubric）」打分；未配置时使用默认标准。"
                : "自动模式：有 exact/contains 时走规则；否则若有 rubric 且已配模型，则走 LLM Judge。"}
            </p>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-ink">Judge 模型（可选）</span>
              <select
                className="input-field w-full"
                value={judgeModelId}
                onChange={(e) => setJudgeModelId(e.target.value)}
              >
                <option value="">使用智能体绑定模型</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.model_type ? ` · ${m.model_type}` : ""}
                  </option>
                ))}
              </select>
            </label>
          </>
        ) : (
          <p className="text-xs text-ink-muted">规则模式仅使用 exact / contains，忽略 rubric。</p>
        )}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    </ResourceDialog>
  );
}

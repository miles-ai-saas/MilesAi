"use client";

import Link from "next/link";
import { ChatArtifactMedia } from "@/components/agent/ChatArtifactMedia";
import type { FlowRunArtifact } from "@/lib/flow-run-artifacts";

type Props = {
  artifacts: FlowRunArtifact[];
};

/** 流程调试：生图/生视频节点产出预览（鉴权 attachment content）。 */
export function FlowRunArtifactsPreview({ artifacts }: Props) {
  if (!artifacts.length) return null;

  return (
    <div className="shrink-0 border-b border-line px-3 py-2">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink-muted">
          生成物预览
          <span className="ml-1 font-normal text-ink-faint">({artifacts.length})</span>
        </span>
        <Link href="/workbench/media-assets" className="text-xs text-brand hover:underline">
          打开生成素材库
        </Link>
      </div>
      <div className="flex max-h-48 flex-wrap gap-3 overflow-y-auto">
        {artifacts.map((a) => (
          <div key={`${a.kind}-${a.attachmentId}`} className="min-w-0">
            {a.label && <p className="mb-1 max-w-[14rem] truncate text-[10px] text-ink-faint">{a.label}</p>}
            <ChatArtifactMedia kind={a.kind} attachmentId={a.attachmentId} mimeType={a.mimeType} caption={a.kind === "image" ? "流程生图" : "流程生视频"} />
          </div>
        ))}
      </div>
    </div>
  );
}

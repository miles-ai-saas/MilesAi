/** 生成任务 SSE 订阅（鉴权 fetch，非 EventSource）。 */

import { getAccessToken } from "@/lib/auth-store";
import type { GenerativeJobOut } from "@/lib/types";

const baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function parseSseData(line: string): GenerativeJobOut | null {
  if (!line.startsWith("data: ")) return null;
  try {
    return JSON.parse(line.slice(6)) as GenerativeJobOut;
  } catch {
    return null;
  }
}

export async function subscribeGenerativeJobStream(jobId: string, onEvent: (job: GenerativeJobOut) => void, signal?: AbortSignal): Promise<void> {
  const token = getAccessToken();
  const res = await fetch(`${baseURL}/generative/jobs/${jobId}/stream`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!res.ok) {
    throw new Error(`进度流连接失败 (${res.status})`);
  }
  const reader = res.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const block of parts) {
      for (const line of block.split("\n")) {
        const job = parseSseData(line.trim());
        if (job) onEvent(job);
      }
    }
  }
}

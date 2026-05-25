"use client";

/**
 * 单技能编辑器：左侧文件树，主区编辑 SKILL.md（或其它文本文件）。
 * 保存调用 putSkillFile；保存 SKILL.md 时后端同步 name/description。
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, getApiErrorMessage } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { SkillFileNode, SkillPackage } from "@/lib/types";

const DEFAULT_PATH = "SKILL.md";

function flattenFiles(nodes: SkillFileNode[]): SkillFileNode[] {
  const out: SkillFileNode[] = [];
  for (const n of nodes) {
    if (n.type === "file") out.push(n);
    if (n.children?.length) out.push(...flattenFiles(n.children));
  }
  return out;
}

export default function SkillEditorPage() {
  const params = useParams();
  const id = String(params.id ?? "");
  const { ready } = useRequireAuth();
  const [skill, setSkill] = useState<SkillPackage | null>(null);
  const [files, setFiles] = useState<SkillFileNode[]>([]);
  const [activePath, setActivePath] = useState(DEFAULT_PATH);
  const [content, setContent] = useState("");
  const [saved, setSaved] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const loadFile = useCallback(
    async (path: string) => {
      const f = await api.getSkillFile(id, path);
      setContent(f.content);
      setSaved(true);
    },
    [id],
  );

  useEffect(() => {
    if (!ready || !id) return;
    setLoading(true);
    setErr("");
    Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)])
      .then(([s, tree]) => {
        setSkill(s);
        setFiles(tree);
        const flat = flattenFiles(tree);
        const path = flat.find((f) => f.path === DEFAULT_PATH)?.path ?? flat[0]?.path ?? DEFAULT_PATH;
        setActivePath(path);
        return api.getSkillFile(id, path);
      })
      .then((f) => setContent(f.content))
      .catch((e) => setErr(getApiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [ready, id]);

  useEffect(() => {
    if (!ready || !id || loading) return;
    void loadFile(activePath).catch((e) => setErr(getApiErrorMessage(e)));
  }, [activePath, ready, id, loading, loadFile]);

  const onSave = async () => {
    setSaving(true);
    setErr("");
    try {
      await api.putSkillFile(id, { path: activePath, content });
      setSaved(true);
      const s = await api.getSkillPackage(id);
      setSkill(s);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const onCreatePack = async () => {
    setErr("请在列表页通过「创建技能包」完成打包（后续可接后端打包 API）");
  };

  const fileList = flattenFiles(files);

  if (loading) {
    return <p className="p-8 text-sm text-ink-muted">加载中…</p>;
  }

  if (!skill) {
    return (
      <div className="p-8">
        <p className="text-red-600">{err || "技能包不存在"}</p>
        <Link href="/workbench/skills" className="mt-4 text-sm text-brand hover:underline">
          返回列表
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-3">
          <Link href="/workbench/skills" className="text-ink-muted hover:text-ink">
            ←
          </Link>
          <h1 className="text-lg font-semibold text-ink">{skill.name}</h1>
          <span className="text-xs text-ink-muted">{skill.slug}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs ${saved ? "text-green-600" : "text-amber-600"}`}>
            {saved ? "已保存" : "未保存"}
          </span>
          <button type="button" className="btn-primary text-sm" disabled={saving} onClick={onSave}>
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-56 shrink-0 border-r border-line bg-surface-elevated p-3">
          <p className="mb-2 text-xs font-medium text-ink-muted">文件</p>
          <ul className="space-y-1 text-sm">
            {fileList.map((f) => (
              <li key={f.path}>
                <button
                  type="button"
                  className={`w-full truncate rounded px-2 py-1 text-left ${
                    activePath === f.path ? "bg-brand/10 text-brand" : "hover:bg-surface-muted"
                  }`}
                  onClick={() => {
                    setActivePath(f.path);
                    setSaved(false);
                  }}
                >
                  {f.name}
                </button>
              </li>
            ))}
            {fileList.length === 0 && (
              <li className="text-xs text-ink-faint">无文件，保存后将生成 SKILL.md</li>
            )}
          </ul>
          <button
            type="button"
            className="mt-6 w-full text-left text-xs text-red-600 hover:underline"
            onClick={onCreatePack}
          >
            创建技能包
          </button>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col p-4">
          <p className="mb-2 text-xs text-ink-muted">{activePath}</p>
          <textarea
            className="input-field min-h-0 flex-1 font-mono text-sm leading-relaxed"
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setSaved(false);
            }}
            spellCheck={false}
          />
          {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
        </main>
      </div>
    </div>
  );
}

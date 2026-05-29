"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api, getApiErrorMessage } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import {
  flattenSkillFiles,
  groupSkillFiles,
  SKILL_EDITOR_DEFAULT_PATH,
  SKILL_NEW_FILE_TEMPLATES,
  skillLayoutSummary,
  skillLayoutWarnings,
} from "@/lib/skill-editor-shared";
import type { SkillFileNode, SkillPackage } from "@/lib/types";

export function useSkillEditorPage() {
  const params = useParams();
  const id = String(params.id ?? "");
  const { ready } = useRequireAuth();
  const [skill, setSkill] = useState<SkillPackage | null>(null);
  const [files, setFiles] = useState<SkillFileNode[]>([]);
  const [activePath, setActivePath] = useState(SKILL_EDITOR_DEFAULT_PATH);
  const [content, setContent] = useState("");
  const [saved, setSaved] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [creatingFile, setCreatingFile] = useState(false);
  const [newFilePrefix, setNewFilePrefix] = useState<"references" | "scripts" | "assets">("references");
  const [newFileName, setNewFileName] = useState("");
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
        const flat = flattenSkillFiles(tree);
        const path = flat.find((f) => f.path === SKILL_EDITOR_DEFAULT_PATH)?.path ?? flat[0]?.path ?? SKILL_EDITOR_DEFAULT_PATH;
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
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const onReindex = async () => {
    setReindexing(true);
    setErr("");
    try {
      const s = await api.reindexSkillPackage(id);
      setSkill(s);
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setReindexing(false);
    }
  };

  const onCreateFile = async () => {
    const raw = newFileName.trim();
    if (!raw) return;
    setCreatingFile(true);
    setErr("");
    try {
      const { path, content: fileContent } = SKILL_NEW_FILE_TEMPLATES[newFilePrefix](raw);
      await api.putSkillFile(id, { path, content: fileContent });
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
      setActivePath(path);
      setContent(fileContent);
      setSaved(true);
      setNewFileName("");
    } catch (e) {
      setErr(getApiErrorMessage(e));
    } finally {
      setCreatingFile(false);
    }
  };

  const onDeleteFile = async (path: string) => {
    if (path === SKILL_EDITOR_DEFAULT_PATH) return;
    if (!window.confirm(`确定删除 ${path}？`)) return;
    setErr("");
    try {
      await api.deleteSkillFile(id, path);
      const [s, tree] = await Promise.all([api.getSkillPackage(id), api.listSkillFiles(id)]);
      setSkill(s);
      setFiles(tree);
      if (activePath === path) {
        setActivePath(SKILL_EDITOR_DEFAULT_PATH);
        await loadFile(SKILL_EDITOR_DEFAULT_PATH);
      }
    } catch (e) {
      setErr(getApiErrorMessage(e));
    }
  };

  const onCreatePack = () => {
    setErr("请在列表页通过「创建技能包」完成打包（后续可接后端打包 API）");
  };

  const selectPath = (path: string) => {
    setActivePath(path);
    setSaved(false);
  };

  const updateContent = (value: string) => {
    setContent(value);
    setSaved(false);
  };

  const fileGroups = useMemo(() => groupSkillFiles(files), [files]);
  const warnings = useMemo(() => skillLayoutWarnings(skill?.config), [skill?.config]);
  const indexSummary = useMemo(() => skillLayoutSummary(skill?.config), [skill?.config]);

  return {
    skill,
    loading,
    err,
    saved,
    saving,
    activePath,
    content,
    fileGroups,
    warnings,
    indexSummary,
    reindexing,
    creatingFile,
    newFilePrefix,
    setNewFilePrefix,
    newFileName,
    setNewFileName,
    onSave,
    onReindex,
    onCreateFile,
    onDeleteFile,
    onCreatePack,
    selectPath,
    updateContent,
  };
}

export type SkillEditorPageVm = ReturnType<typeof useSkillEditorPage>;

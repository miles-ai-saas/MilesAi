"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { filterBySearch } from "@/lib/filter-search";
import type { KnowledgeBase, MediaAsset } from "@/lib/types";

export function useMediaAssetsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [promoted, setPromoted] = useState<"" | "yes" | "no">("");
  const [msg, setMsg] = useState("");
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [promoteTarget, setPromoteTarget] = useState<MediaAsset | null>(null);
  const [promoteKbId, setPromoteKbId] = useState("");
  const [promoteBusy, setPromoteBusy] = useState(false);

  const list = usePagedList(
    useCallback(
      (p, s) =>
        api.listMediaAssets(p, s, {
          kind: kind || undefined,
          has_kb_document: promoted === "yes" ? true : promoted === "no" ? false : undefined,
        }),
      [kind, promoted],
    ),
    { enabled: ready, resetKey: `${kind}-${promoted}` },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  useEffect(() => {
    if (!ready) return;
    void api.listKbs(1, 100).then((r) => setKbs(r.items));
  }, [ready]);

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (a) => `${a.title ?? ""} ${a.prompt ?? ""} ${a.kind} ${a.source} ${a.attachment?.filename ?? ""}`.trim()),
    [list.items, search],
  );

  const onDelete = (a: MediaAsset) => {
    requestConfirm({
      title: "删除素材",
      message: <>确定删除「{a.title ?? a.attachment?.filename ?? a.id}」？</>,
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteMediaAsset(a.id);
        await list.reload();
        setMsg("已删除");
      },
    });
  };

  const openPromote = (a: MediaAsset) => {
    setPromoteTarget(a);
    setPromoteKbId(kbs[0]?.id ?? "");
    setMsg("");
  };

  const onPromote = async () => {
    if (!promoteTarget || !promoteKbId) return;
    setPromoteBusy(true);
    setMsg("");
    try {
      await api.promoteMediaAssetToKb(promoteTarget.id, {
        kb_id: promoteKbId,
        filename: promoteTarget.title ?? promoteTarget.attachment?.filename,
        run_parse: true,
      });
      setPromoteTarget(null);
      await list.reload();
      setMsg("已加入知识库并开始解析");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "升格失败");
    } finally {
      setPromoteBusy(false);
    }
  };

  return {
    search,
    setSearch,
    kind,
    setKind,
    promoted,
    setPromoted,
    msg,
    kbs,
    promoteTarget,
    setPromoteTarget,
    promoteKbId,
    setPromoteKbId,
    promoteBusy,
    list,
    filtered,
    confirmDialog,
    onDelete,
    openPromote,
    onPromote,
  };
}

export type MediaAssetsPageVm = ReturnType<typeof useMediaAssetsPage>;

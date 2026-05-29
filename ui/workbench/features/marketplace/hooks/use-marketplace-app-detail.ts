"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { AppRating, MarketplaceAppDetail } from "@/lib/types";

type Params = {
  setMsg: (msg: string) => void;
  reloadApps: () => Promise<void>;
};

export function useMarketplaceAppDetail({ setMsg, reloadApps }: Params) {
  const [detailAppId, setDetailAppId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MarketplaceAppDetail | null>(null);
  const [detailRatings, setDetailRatings] = useState<AppRating[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [rateScore, setRateScore] = useState(5);
  const [rateComment, setRateComment] = useState("");
  const [rateSaving, setRateSaving] = useState(false);

  const loadDetail = useCallback(async (appId: string) => {
    setDetailAppId(appId);
    setDetailLoading(true);
    setDetail(null);
    setDetailRatings([]);
    try {
      const [d, ratings] = await Promise.all([api.getMarketplaceApp(appId), api.listMarketplaceAppRatings(appId, 1, 20)]);
      setDetail(d);
      setDetailRatings(ratings.items);
      if (d.my_rating) {
        setRateScore(d.my_rating.score);
        setRateComment(d.my_rating.comment ?? "");
      } else {
        setRateScore(5);
        setRateComment("");
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载详情失败");
      setDetailAppId(null);
    } finally {
      setDetailLoading(false);
    }
  }, [setMsg]);

  const closeDetail = useCallback(() => {
    setDetailAppId(null);
    setDetail(null);
  }, []);

  const onSaveRating = useCallback(async () => {
    if (!detailAppId || !detail?.installed) return;
    setRateSaving(true);
    try {
      await api.rateMarketplaceApp(detailAppId, {
        score: rateScore,
        comment: rateComment.trim() || undefined,
      });
      setMsg("评分已保存");
      await loadDetail(detailAppId);
      await reloadApps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "评分失败");
    } finally {
      setRateSaving(false);
    }
  }, [detail?.installed, detailAppId, loadDetail, rateComment, rateScore, reloadApps, setMsg]);

  const onDeleteRating = useCallback(async () => {
    if (!detailAppId) return;
    setRateSaving(true);
    try {
      await api.deleteMyMarketplaceRating(detailAppId);
      setMsg("已删除评分");
      await loadDetail(detailAppId);
      await reloadApps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setRateSaving(false);
    }
  }, [detailAppId, loadDetail, reloadApps, setMsg]);

  return {
    detailAppId,
    detail,
    detailRatings,
    detailLoading,
    rateScore,
    setRateScore,
    rateComment,
    setRateComment,
    rateSaving,
    loadDetail,
    closeDetail,
    onSaveRating,
    onDeleteRating,
  };
}

export type MarketplaceAppDetailState = ReturnType<typeof useMarketplaceAppDetail>;

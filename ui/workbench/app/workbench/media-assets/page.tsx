"use client";

/** 生成物媒体资产：列表、预览、升格入库。 */

import { MediaAssetsPageView, useMediaAssetsPage } from "@/features/media-assets";

export default function MediaAssetsPage() {
  const vm = useMediaAssetsPage();
  return <MediaAssetsPageView vm={vm} />;
}

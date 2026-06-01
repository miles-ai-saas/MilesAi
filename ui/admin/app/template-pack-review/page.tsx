"use client";

import { TemplatePackReviewPageView } from "@/components/template-packs/TemplatePackReviewPageView";
import { useTemplatePackReviewPage } from "@/hooks/use-template-pack-review-page";

export default function TemplatePackReviewPage() {
  const vm = useTemplatePackReviewPage();
  return <TemplatePackReviewPageView vm={vm} />;
}

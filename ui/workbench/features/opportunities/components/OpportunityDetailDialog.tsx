"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { OpportunityDetailView, useOpportunityDetailPage } from "@/features/opportunities/components/OpportunityDetailView";

type Props = {
  opportunityId: string | null;
  onClose: () => void;
  onMutated?: () => void;
};

export function OpportunityDetailDialog({ opportunityId, onClose, onMutated }: Props) {
  const vm = useOpportunityDetailPage(opportunityId ?? "", { onMutated });

  return (
    <ResourceDialog
      open={Boolean(opportunityId)}
      title={vm.opp?.name ?? "商机详情"}
      description={vm.opp?.code ?? undefined}
      onClose={onClose}
      size="lg"
    >
      <OpportunityDetailView vm={vm} embedded onClose={onClose} />
    </ResourceDialog>
  );
}

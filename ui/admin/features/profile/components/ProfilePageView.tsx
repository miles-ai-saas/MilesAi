"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { ProfilePasswordSection, ProfileSessionsSection } from "@/features/profile/components/ProfileSections";
import type { ProfilePageVm } from "@/features/profile/hooks/use-profile-page";
import { PROFILE_PAGE_DESCRIPTION } from "@/features/profile/lib/profile-page-shared";

export function ProfilePageView({ vm }: { vm: ProfilePageVm }) {
  const { me } = vm;

  return (
    <div className="admin-page-stack max-w-lg">
      <PageHeader title="账号安全" description={PROFILE_PAGE_DESCRIPTION} />

      {me && (
        <p className="text-sm text-ink-muted">
          当前账号：<span className="font-medium text-ink">{me.username}</span>
          <span className="text-ink-faint"> · {me.role}</span>
        </p>
      )}

      <ProfilePasswordSection vm={vm} />
      <ProfileSessionsSection vm={vm} />
    </div>
  );
}

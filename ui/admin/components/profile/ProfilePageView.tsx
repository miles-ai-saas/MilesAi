"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { ProfilePasswordSection, ProfileSessionsSection } from "@/components/profile/ProfileSections";
import type { ProfilePageVm } from "@/hooks/use-profile-page";
import { PROFILE_PAGE_DESCRIPTION } from "@/lib/profile-page-shared";

export function ProfilePageView({ vm }: { vm: ProfilePageVm }) {
  const { me } = vm;

  return (
    <div className="max-w-lg">
      <PageHeader title="账号安全" description={PROFILE_PAGE_DESCRIPTION} />

      {me && (
        <p className="mb-6 text-sm text-ink-muted">
          当前账号：<span className="font-medium text-ink">{me.username}</span>
          <span className="text-ink-faint"> · {me.role}</span>
        </p>
      )}

      <ProfilePasswordSection vm={vm} />
      <ProfileSessionsSection vm={vm} />
    </div>
  );
}

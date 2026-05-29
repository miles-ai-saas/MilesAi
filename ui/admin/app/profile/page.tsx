"use client";

import { ProfilePageView } from "@/components/profile/ProfilePageView";
import { useProfilePage } from "@/hooks/use-profile-page";

export default function ProfilePage() {
  const vm = useProfilePage();
  return <ProfilePageView vm={vm} />;
}

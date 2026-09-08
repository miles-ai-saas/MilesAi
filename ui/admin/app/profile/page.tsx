"use client";

export default function ProfilePage() {
  const vm = useProfilePage();
  return <ProfilePageView vm={vm} />;
}
import { ProfilePageView, useProfilePage } from "@/features/profile";

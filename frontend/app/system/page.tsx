import { redirect } from "next/navigation";

export default function SystemHomePage() {
  redirect("/system/users");
}

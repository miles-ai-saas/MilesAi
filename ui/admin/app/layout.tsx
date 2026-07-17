import type { Metadata } from "next";
import { AdminShell } from "@/components/layout/AdminShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "管理后台",
  description: "平台租户、计费与风控管理",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="font-sans antialiased">
        <AdminShell>{children}</AdminShell>
      </body>
    </html>
  );
}

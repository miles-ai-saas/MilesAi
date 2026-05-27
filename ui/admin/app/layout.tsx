import type { Metadata } from "next";
import { AdminShell } from "@/components/layout/AdminShell";
import "./globals.css";
import { appFont } from "@/lib/fonts";

export const metadata: Metadata = {
  title: "MilesAi 管理后台",
  description: "平台租户、计费与风控管理",
  icons: {
    icon: "/brand/logo-mark.svg",
    apple: "/brand/logo-mark.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={appFont.variable}>
      <body className={`${appFont.className} font-sans antialiased`}>
        <AdminShell>{children}</AdminShell>
      </body>
    </html>
  );
}

/** Next 根布局：字体 token、`AppShell` 包裹全站（链路 §7）。 */

import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";
import { appFont } from "@/lib/fonts";

export const metadata: Metadata = {
  title: "行千里",
  description: "AI 智能编排与 RAG 平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={appFont.variable}>
      <body className={`${appFont.className} font-sans antialiased`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

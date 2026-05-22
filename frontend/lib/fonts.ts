import { Noto_Sans_SC } from "next/font/google";

import { fontFamilySans } from "./font-family";

export { fontFamilySans };

/** 与 docs/frontend/design.md 一致的应用字体（租户端 / 运营端共用配置） */
export const appFont = Noto_Sans_SC({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  preload: true,
});

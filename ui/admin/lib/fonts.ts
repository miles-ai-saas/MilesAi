import { Noto_Sans_SC } from "next/font/google";

import { fontFamilySans } from "./font-family";

export { fontFamilySans };

/** 与租户工作台一致（见 ui/workbench/lib/fonts.ts） */
export const appFont = Noto_Sans_SC({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  preload: true,
});

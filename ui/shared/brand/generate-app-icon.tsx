import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ImageResponse } from "next/og";

import { COMPANY_ORANGE } from "./company-logo";

const FONT_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fonts/noto-sans-sc-bold-subset.ttf",
);

let fontCache: ArrayBuffer | null = null;

async function loadBoldFont() {
  if (fontCache) return fontCache;
  const buf = await readFile(FONT_PATH);
  fontCache = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  return fontCache;
}

/** 生成品牌应用图标（favicon / Apple Touch Icon）：行千里 mark。 */
export async function generateAppIcon(size: number) {
  const fontData = await loadBoldFont();

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#FEF3EE",
          borderRadius: size * 0.2,
        }}
      >
        <div
          style={{
            fontSize: size * 0.3,
            fontWeight: 700,
            color: COMPANY_ORANGE,
            fontFamily: "Noto Sans SC",
            lineHeight: 1,
            letterSpacing: "-0.04em",
          }}
        >
          行千里
        </div>
      </div>
    ),
    {
      width: size,
      height: size,
      fonts: [
        {
          name: "Noto Sans SC",
          data: fontData,
          weight: 700,
          style: "normal",
        },
      ],
    },
  );
}

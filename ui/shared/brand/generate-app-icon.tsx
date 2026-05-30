import { ImageResponse } from "next/og";

import { COMPANY_ORANGE } from "./company-logo";

const NOTO_SANS_SC_BOLD =
  "https://fonts.gstatic.com/s/notosanssc/v40/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf";

async function loadBoldFont() {
  const response = await fetch(NOTO_SANS_SC_BOLD);
  if (!response.ok) {
    throw new Error("Failed to load Noto Sans SC for app icon");
  }
  return response.arrayBuffer();
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

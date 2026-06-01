/** 带鉴权下载 CSV/文件（读取 Content-Disposition 文件名）。 */

import { http } from "@/lib/api/client";

export async function downloadAuthenticatedFile(url: string, fallbackFilename: string): Promise<void> {
  const res = await http.get(url, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] as string | undefined;
  const match = disposition?.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? fallbackFilename;
  const blobUrl = URL.createObjectURL(res.data as Blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(blobUrl);
}

"use client";

import { useState } from "react";
import { downloadAuthenticatedFile } from "@/lib/download-file";

export function ExportCsvButton({
  url,
  filename,
  label = "导出 CSV",
  className = "btn-sm-outline text-sm",
}: {
  url: string;
  filename: string;
  label?: string;
  className?: string;
}) {
  const [loading, setLoading] = useState(false);

  return (
    <button
      type="button"
      className={className}
      disabled={loading}
      onClick={() => {
        setLoading(true);
        void downloadAuthenticatedFile(url, filename)
          .catch((e) => alert(e?.message ?? "导出失败"))
          .finally(() => setLoading(false));
      }}
    >
      {loading ? "导出中…" : label}
    </button>
  );
}

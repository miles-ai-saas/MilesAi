export function kbFileIcon(filename: string): string {
  const ext = filename.includes(".") ? filename.slice(filename.lastIndexOf(".")).toLowerCase() : "";
  if ([".pdf"].includes(ext)) return "PDF";
  if ([".docx", ".doc"].includes(ext)) return "DOC";
  if ([".pptx", ".ppt"].includes(ext)) return "PPT";
  if ([".xlsx", ".xls"].includes(ext)) return "XLS";
  if ([".md", ".markdown", ".txt"].includes(ext)) return "TXT";
  if ([".jpg", ".jpeg", ".png", ".webp"].includes(ext)) return "IMG";
  if ([".mp3", ".wav", ".m4a", ".ogg", ".webm"].includes(ext)) return "AUD";
  if ([".html", ".htm"].includes(ext)) return "WEB";
  return "FILE";
}

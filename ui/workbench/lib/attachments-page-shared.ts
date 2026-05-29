export const ATTACHMENTS_PAGE_DESC = "租户级通用文件存储，可用于对话、智能体等场景；占用与知识库文档合计的存储配额。";

export function formatAttachmentBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

/** 上传 accept 与大小限制（链路 §8 文档上传）。 */

/**
 * 与 backend `app/rag/parse/upload_policy.KB_ALLOWED_EXTENSIONS` 保持一致。
 */
export const KB_UPLOAD_ACCEPT =
  ".docx,.htm,.html,.jpeg,.jpg,.m4a,.markdown,.md,.mp3,.ogg,.pdf,.png,.pptx,.txt,.wav,.webm,.webp,.xlsx";

export const KB_UPLOAD_HINT =
  "支持 TXT/MD/PDF、Office（DOCX/PPTX/XLSX/HTML）、图片、音频；入库后可在「检索测试」验证";

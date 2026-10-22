export const DOCUMENT_MAX_FILE_SIZE = 20 * 1024 * 1024;
export const DOCUMENT_UPLOAD_TIMEOUT_MS = 180_000;

export function documentFileError(file: Pick<File, "name" | "size">): string | null {
  if (!file.name.trim() || file.name.length > 500) return "Tên file không hợp lệ hoặc dài quá 500 ký tự.";
  if (!/\.(pdf|docx)$/i.test(file.name)) return "Chỉ hỗ trợ file PDF hoặc DOCX.";
  if (file.size === 0) return "File đang trống. Vui lòng chọn file có nội dung.";
  if (file.size > DOCUMENT_MAX_FILE_SIZE) return "Dung lượng file không được vượt quá 20 MB.";
  return null;
}

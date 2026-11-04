import type { Evidence, ExtractedField } from "@/interface/Extraction/Extraction.interface";

export const fieldLabels = { deadline: "Thời hạn", obligation: "Nghĩa vụ", applicable_subject: "Đối tượng áp dụng", legal_basis: "Căn cứ pháp lý" };
export const reviewLabels = { pending: "Chờ duyệt", approved: "Đã duyệt", rejected: "Đã từ chối" };
export const runLabels = { pending: "Đang chờ", processing: "Đang trích xuất", completed: "Hoàn tất", failed: "Thất bại" };

export function fieldDisplayValue(field: ExtractedField): string {
  if (field.reviewed_value !== null) return field.reviewed_value;
  const date = field.normalized_value.date;
  if (field.field_key === "deadline" && typeof date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return date.split("-").reverse().join("/");
  }
  return field.raw_value;
}

export function evidenceParts(evidence: Evidence) {
  // Python offsets count Unicode code points; JS slice counts UTF-16 units.
  const chars = Array.from(evidence.segment_content_snapshot);
  const { start_offset: start, end_offset: end } = evidence;
  if (start < 0 || end <= start || end > chars.length || chars.slice(start, end).join("") !== evidence.quote) return null;
  return { before: chars.slice(0, start).join(""), quote: evidence.quote, after: chars.slice(end).join("") };
}

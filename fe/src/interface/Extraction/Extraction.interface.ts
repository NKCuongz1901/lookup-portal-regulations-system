import type { PaginationMeta } from "@/interface/common/common.interface";

export type FieldKey = "deadline" | "obligation" | "applicable_subject" | "legal_basis";
export type ReviewStatus = "pending" | "approved" | "rejected";
export interface ExtractionRun {
  id: number; document_version_id: number;
  status: "pending" | "processing" | "completed" | "failed";
  field_count: number; attempt_count: number; rule_version: string;
  created_at: string; finished_at: string | null; lease_expires_at: string | null;
  warnings: string[]; error_code: string | null; error_message: string | null;
}
export interface Evidence {
  id: number; document_segment_id: number | null; source_segment_id: number;
  segment_index: number; page_number: number | null; section_title: string | null;
  segment_content_snapshot: string; quote: string; start_offset: number; end_offset: number;
  role: "value" | "context"; occurrence_index: number;
}
export interface ExtractedField {
  id: number; extraction_run_id: number; field_key: FieldKey; item_index: number;
  raw_value: string; normalized_value: Record<string, unknown>; review_status: ReviewStatus;
  review_revision: number; reviewed_value: string | null; reviewed_at: string | null;
  evidences: Evidence[];
}
export interface FieldReview {
  id: number; revision: number; action: "approve" | "correct" | "reject";
  previous_status: ReviewStatus; new_status: ReviewStatus;
  previous_value: string; new_value: string; note: string | null;
  reviewer_id: number | null; reviewer_name: string; created_at: string;
}
export interface ReviewPayload {
  action: FieldReview["action"]; expected_revision: number; idempotency_key: string;
  corrected_value?: string; note?: string;
}
export interface FieldFilters { page?: number; itemsPerPage?: number; field_key?: FieldKey; review_status?: ReviewStatus }
export type PageMeta = PaginationMeta;

import type { ListParams } from "@/interface/common/common.interface";

export type PublicationStatus = "draft" | "published" | "hidden" | "archived";
export interface Lookup {
  id: number;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}
export interface DocumentTag { id: number; name: string; slug: string }
export interface DocumentItem {
  id: number;
  code: string;
  title: string;
  document_type_id: number | null;
  issuing_unit_id: number | null;
  document_type: Lookup | null;
  issuing_unit: Lookup | null;
  tags: DocumentTag[];
  issue_date: string | null;
  effective_from: string | null;
  effective_until: string | null;
  academic_year: string | null;
  publication_status: PublicationStatus;
  created_at: string;
  updated_at: string;
}
export interface DocumentDetail extends DocumentItem {
  description: string | null;
  applicable_subject_codes: string[];
  published_at: string | null;
  created_by: number;
  updated_by: number | null;
}
export interface DocumentFilters extends ListParams {
  publication_status?: PublicationStatus;
  document_type_id?: number;
  issuing_unit_id?: number;
  tag_id?: number;
  academic_year?: string;
}

export interface DocumentCreatePayload {
  code: string;
  title: string;
  description?: string | null;
  document_type_id?: number | null;
  issuing_unit_id?: number | null;
  issue_date?: string | null;
  effective_from?: string | null;
  effective_until?: string | null;
  academic_year?: string | null;
  applicable_subject_codes: string[];
  tag_ids: number[];
}

export type DocumentUpdatePayload = Partial<DocumentCreatePayload>;

export interface StoredFile {
  id: number;
  storage_provider: string;
  storage_key: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string | null;
  uploaded_by: number | null;
  created_at: string;
}

export interface DocumentVersion {
  id: number;
  document_id: number;
  version_number: number;
  file_id: number;
  is_current: boolean;
  parse_status: "pending" | "processing" | "parsed" | "failed";
  parser_version: string | null;
  parsed_at: string | null;
  created_by: number;
  created_at: string;
  file: StoredFile;
}

export interface DocumentDownload {
  document_id: number;
  version_id: number;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  url: string;
  expires_in: number;
}

export type DocumentVersionParams = Pick<ListParams, "page" | "itemsPerPage">;

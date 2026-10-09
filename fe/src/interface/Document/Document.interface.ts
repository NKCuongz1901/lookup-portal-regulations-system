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

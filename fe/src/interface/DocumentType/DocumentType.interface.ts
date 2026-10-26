import type { Lookup } from "@/interface/Document/Document.interface";
import type { ListParams } from "@/interface/common/common.interface";

export interface DocumentType extends Lookup {
  created_at: string;
}

export interface DocumentTypeFilters extends ListParams {
  is_active?: boolean;
}

export interface DocumentTypePayload {
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export type DocumentTypeUpdatePayload = Partial<DocumentTypePayload>;

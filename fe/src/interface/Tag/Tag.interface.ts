import type { DocumentTag } from "@/interface/Document/Document.interface";
import type { ListParams } from "@/interface/common/common.interface";

export interface TagItem extends DocumentTag {
  created_at: string;
}

export type TagFilters = ListParams;
export interface TagPayload {
  name: string;
  slug: string;
}
export type TagUpdatePayload = Partial<TagPayload>;

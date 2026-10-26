import type { Lookup } from "@/interface/Document/Document.interface";
import type { ListParams } from "@/interface/common/common.interface";

export interface IssuingUnit extends Lookup {
  created_at: string;
}

export interface IssuingUnitFilters extends ListParams {
  is_active?: boolean;
}

export interface IssuingUnitPayload {
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export type IssuingUnitUpdatePayload = Partial<IssuingUnitPayload>;

import dayjs, { type Dayjs } from "dayjs";
import type { DocumentCreatePayload, DocumentDetail, DocumentUpdatePayload } from "@/interface/Document/Document.interface";

export interface DocumentFormValues extends Omit<DocumentCreatePayload, "issue_date" | "effective_from" | "effective_until"> {
  issue_date?: Dayjs | null;
  effective_from?: Dayjs | null;
  effective_until?: Dayjs | null;
}

export function documentInitialValues(document?: DocumentDetail): Partial<DocumentFormValues> {
  if (!document) return { applicable_subject_codes: [], tag_ids: [] };
  return {
    code: document.code, title: document.title, description: document.description,
    document_type_id: document.document_type_id, issuing_unit_id: document.issuing_unit_id,
    issue_date: document.issue_date ? dayjs(document.issue_date) : null,
    effective_from: document.effective_from ? dayjs(document.effective_from) : null,
    effective_until: document.effective_until ? dayjs(document.effective_until) : null,
    academic_year: document.academic_year,
    applicable_subject_codes: [...document.applicable_subject_codes],
    tag_ids: document.tags.map((tag) => tag.id),
  };
}

export function documentFormPayload(values: DocumentFormValues): DocumentCreatePayload {
  return {
    code: values.code.trim(), title: values.title.trim(),
    description: values.description?.trim() || null,
    academic_year: values.academic_year?.trim() || null,
    document_type_id: values.document_type_id ?? null, issuing_unit_id: values.issuing_unit_id ?? null,
    issue_date: values.issue_date?.format("YYYY-MM-DD") ?? null,
    effective_from: values.effective_from?.format("YYYY-MM-DD") ?? null,
    effective_until: values.effective_until?.format("YYYY-MM-DD") ?? null,
    applicable_subject_codes: [...new Set((values.applicable_subject_codes ?? []).map((code) => code.trim()).filter(Boolean))],
    tag_ids: [...new Set(values.tag_ids ?? [])],
  };
}

export function documentUpdatePayload(values: DocumentFormValues, original: DocumentDetail): DocumentUpdatePayload {
  const next = documentFormPayload(values);
  const previous = documentFormPayload(documentInitialValues(original) as DocumentFormValues);
  // Keep untouched fields out of PATCH, including existing inactive references.
  return Object.fromEntries(Object.entries(next).filter(([key, value]) =>
    JSON.stringify(value) !== JSON.stringify(previous[key as keyof DocumentCreatePayload])));
}

export function includeCurrentOptions<T extends { id: number }>(available: T[] | undefined, current: T[]): T[] {
  const records = new Map((available ?? []).map((item) => [item.id, item]));
  for (const item of current) if (!records.has(item.id)) records.set(item.id, item);
  return [...records.values()];
}

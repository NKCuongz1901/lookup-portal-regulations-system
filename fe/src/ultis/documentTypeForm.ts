import type { CurrentUser } from "@/interface/Auth/Auth.interface";
import type { DocumentTypePayload, DocumentTypeUpdatePayload } from "@/interface/DocumentType/DocumentType.interface";

export const canManageDocumentTypes = (user: Pick<CurrentUser, "is_active" | "roles">) =>
  user.is_active && user.roles.includes("ADMIN");

export function documentTypePayload(values: DocumentTypePayload): DocumentTypePayload {
  return {
    code: values.code.trim(), name: values.name.trim(),
    description: values.description?.trim() || null,
    is_active: values.is_active,
  };
}

export function documentTypeChanges(values: DocumentTypePayload, original: DocumentTypePayload): DocumentTypeUpdatePayload {
  const next = documentTypePayload(values);
  const previous = documentTypePayload(original);
  return Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== previous[key as keyof DocumentTypePayload]));
}

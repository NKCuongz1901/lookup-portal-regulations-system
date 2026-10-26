import type { CurrentUser } from "@/interface/Auth/Auth.interface";
import type { TagPayload, TagUpdatePayload } from "@/interface/Tag/Tag.interface";

export const canManageTags = (user: Pick<CurrentUser, "is_active" | "roles">) =>
  user.is_active && user.roles.some((role) => role === "ADMIN" || role === "STAFF");

export const TAG_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function tagSlugFromName(name: string): string {
  return name.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[đĐ]/g, "d").toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .slice(0, 120).replace(/^-+|-+$/g, "");
}

export function tagPayload(values: TagPayload): TagPayload {
  return { name: values.name.trim(), slug: values.slug.trim() };
}

export function tagChanges(values: TagPayload, original: TagPayload): TagUpdatePayload {
  const next = tagPayload(values);
  const previous = tagPayload(original);
  return Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== previous[key as keyof TagPayload]));
}

import type { CurrentUser } from "@/interface/Auth/Auth.interface";
import type { IssuingUnitPayload, IssuingUnitUpdatePayload } from "@/interface/IssuingUnit/IssuingUnit.interface";

export const canManageIssuingUnits = (user: Pick<CurrentUser, "is_active" | "roles">) =>
  user.is_active && user.roles.includes("ADMIN");

export function issuingUnitPayload(values: IssuingUnitPayload): IssuingUnitPayload {
  return {
    code: values.code.trim(), name: values.name.trim(),
    description: values.description?.trim() || null,
    is_active: values.is_active,
  };
}

export function issuingUnitChanges(values: IssuingUnitPayload, original: IssuingUnitPayload): IssuingUnitUpdatePayload {
  const next = issuingUnitPayload(values);
  const previous = issuingUnitPayload(original);
  return Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== previous[key as keyof IssuingUnitPayload]));
}

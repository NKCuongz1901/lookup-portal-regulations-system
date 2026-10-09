export const AUTH_ROUTES = {
  login: "/auth/login",
  session: "/auth/session",
  logout: "/auth/logout",
} as const;

export const API_ROUTES = {
  users: "/backend/users",
  documents: "/backend/documents",
  documentTypes: "/backend/document-types",
  issuingUnits: "/backend/issuing-units",
} as const;

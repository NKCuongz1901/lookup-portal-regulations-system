export type Role = "ADMIN" | "STAFF" | "STUDENT";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  student_code: string | null;
  is_active: boolean;
  roles: Role[];
}

export interface LoginPayload {
  email: string;
  password: string;
  remember: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

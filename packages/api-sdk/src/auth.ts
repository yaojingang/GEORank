import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserOut
} from './generated/types.gen';
export type { LoginRequest, RegisterRequest, TokenResponse, UserOut } from './generated/types.gen';

const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export type UserProfileUpdatePayload = {
  email?: string;
  username?: string;
  phone?: string | null;
};

export type PasswordChangePayload = {
  currentPassword: string;
  newPassword: string;
};

async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail || `API ${response.status}`);
  }
  return payload as T;
}

export async function login(body: LoginRequest): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  return parseJson<TokenResponse>(response);
}

export async function register(body: RegisterRequest): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  return parseJson<TokenResponse>(response);
}

export async function getCurrentUser(token: string): Promise<UserOut> {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: 'no-store'
  });
  return parseJson<UserOut>(response);
}

export async function updateCurrentUser(
  token: string,
  payload: UserProfileUpdatePayload
): Promise<UserOut> {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
  return parseJson<UserOut>(response);
}

export async function changePassword(token: string, payload: PasswordChangePayload) {
  const response = await fetch(`${API_BASE}/api/auth/password`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      current_password: payload.currentPassword,
      new_password: payload.newPassword
    })
  });
  return parseJson<{message: string}>(response);
}

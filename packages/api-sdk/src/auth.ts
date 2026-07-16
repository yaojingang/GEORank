import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserOut
} from './generated/types.gen';
import {getDeviceHeaders} from './device';
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

export type UserUsageSummary = {
  access_mode: string;
  daily_token_limit: number;
  lifetime_token_grant: number;
  grant_tokens: number;
  usage_date: string;
  used_tokens: number;
  reserved_tokens: number;
  request_count: number;
  remaining_tokens: number | null;
  quota_state: string;
  principal_id?: string | null;
  linked_user_count: number;
  linked_device_count: number;
  global_budget: {
    enabled: boolean;
    usage_date: string;
    limit_tokens: number;
    used_tokens: number;
    reserved_tokens: number;
    remaining_tokens: number;
    state: string;
  };
  platform_available: boolean;
  reason_code?: string | null;
  byok_guidance: {
    provider?: string;
    title?: string;
    message?: string;
    cta_label?: string;
    official_url?: string;
    base_url?: string;
    model?: string;
  };
  provider_presets: Array<{
    key: string;
    name: string;
    base_url: string;
    default_model: string;
  }>;
  allow_user_byok: boolean;
  byok_transport_mode: string;
  metered_modules: string[];
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
      Authorization: `Bearer ${token}`,
      ...getDeviceHeaders()
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

export async function getMyUsage(token: string): Promise<UserUsageSummary> {
  const response = await fetch(`${API_BASE}/api/usage/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
      ...getDeviceHeaders()
    },
    cache: 'no-store'
  });
  return parseJson<UserUsageSummary>(response);
}

import type { UserOut } from '@georank/api-sdk';
import { getCurrentUser } from '@georank/api-sdk';

import { bindPhone } from './browser-binding';

export const TOKEN_KEY = 'georank_user_token';
export const USER_KEY = 'georank_user_profile';

function getCookie(name: string): string {
  if (typeof document === 'undefined') return '';
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : '';
}

function setCookie(name: string, value: string, days = 365) {
  if (typeof document === 'undefined') return;
  const maxAge = Math.max(0, Math.floor(days * 24 * 60 * 60));
  document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=${maxAge}; Path=/; SameSite=Lax`;
}

function clearCookie(name: string) {
  if (typeof document === 'undefined') return;
  document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax`;
}

function parseUser(raw: string | null): UserOut | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserOut;
  } catch {
    return null;
  }
}

export function getStoredToken(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(TOKEN_KEY) || getCookie(TOKEN_KEY) || '';
}

export function getStoredUser(): UserOut | null {
  if (typeof window === 'undefined') return null;
  return parseUser(localStorage.getItem(USER_KEY));
}

export function setSession(token: string, user: UserOut, remember = true) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  bindPhone(user.phone || '');
  if (remember) {
    setCookie(TOKEN_KEY, token, 365);
  } else {
    document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
  }
}

export function clearSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  clearCookie(TOKEN_KEY);
}

export async function getSession() {
  const token = getStoredToken();
  if (!token) return null;
  const cachedUser = getStoredUser();
  if (cachedUser) return cachedUser;
  try {
    const user = await getCurrentUser(token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    if (user.phone) bindPhone(user.phone);
    return user;
  } catch {
    clearSession();
    return null;
  }
}

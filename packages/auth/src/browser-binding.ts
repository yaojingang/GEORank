export const BOUND_PHONE_KEY = 'georank_browser_phone';

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

export function normalizePhone(phone: string | null | undefined): string {
  const digits = String(phone || '').replace(/\D+/g, '');
  if (digits.startsWith('86') && digits.length === 13) {
    return digits.slice(2);
  }
  return digits;
}

export function maskPhone(phone: string | null | undefined): string {
  const normalized = normalizePhone(phone);
  if (!/^1\d{10}$/.test(normalized)) {
    return phone || '已登录';
  }
  return `${normalized.slice(0, 3)}****${normalized.slice(-4)}`;
}

export function getBoundPhone() {
  if (typeof window === 'undefined') return '';
  return normalizePhone(localStorage.getItem(BOUND_PHONE_KEY) || getCookie(BOUND_PHONE_KEY));
}

export function bindPhone(phone: string) {
  const normalized = normalizePhone(phone);
  if (!normalized || typeof window === 'undefined') return;
  localStorage.setItem(BOUND_PHONE_KEY, normalized);
  setCookie(BOUND_PHONE_KEY, normalized, 365);
}

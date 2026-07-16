import {getDeviceHeaders} from './device';

export const BYOK_STORAGE_KEY = 'georank_byok_config_v1';

export type ByokConfig = {
  enabled: boolean;
  provider: string;
  baseUrl: string;
  model: string;
  apiKey: string;
};

export const DEFAULT_BYOK_CONFIG: ByokConfig = {
  enabled: false,
  provider: 'deepseek',
  baseUrl: 'https://api.deepseek.com',
  model: 'deepseek-v4-flash',
  apiKey: ''
};

function cleanHeaderValue(value: unknown, limit: number) {
  return String(value || '').replace(/[\r\n]+/g, '').trim().slice(0, limit);
}

function normalizeByokConfig(value: unknown): ByokConfig {
  const stored = value && typeof value === 'object' ? value as Partial<Record<keyof ByokConfig, unknown>> : {};
  return {
    enabled: Boolean(stored.enabled),
    provider: cleanHeaderValue(stored.provider || DEFAULT_BYOK_CONFIG.provider, 50) || DEFAULT_BYOK_CONFIG.provider,
    baseUrl: cleanHeaderValue(stored.baseUrl || DEFAULT_BYOK_CONFIG.baseUrl, 240),
    model: cleanHeaderValue(stored.model || DEFAULT_BYOK_CONFIG.model, 100),
    apiKey: cleanHeaderValue(stored.apiKey, 1000)
  };
}

export function isValidByokBaseUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:';
  } catch {
    return false;
  }
}

export function readByokConfig(): ByokConfig | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(BYOK_STORAGE_KEY);
  if (!raw) return null;
  try {
    return normalizeByokConfig(JSON.parse(raw));
  } catch {
    window.localStorage.removeItem(BYOK_STORAGE_KEY);
    return null;
  }
}

export function saveByokConfig(value: ByokConfig) {
  const config = normalizeByokConfig(value);
  window.localStorage.setItem(BYOK_STORAGE_KEY, JSON.stringify({...config, updatedAt: new Date().toISOString()}));
  return config;
}

export function clearByokConfig() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(BYOK_STORAGE_KEY);
}

export function getByokHeaders(): Record<string, string> {
  const config = readByokConfig();
  if (
    !config?.enabled ||
    !config.apiKey ||
    !config.model ||
    !isValidByokBaseUrl(config.baseUrl)
  ) {
    return getDeviceHeaders();
  }
  return {
    ...getDeviceHeaders(),
    'X-GEOrank-BYOK-Provider': config.provider,
    'X-GEOrank-BYOK-Base-URL': config.baseUrl,
    'X-GEOrank-BYOK-Model': config.model,
    'X-GEOrank-BYOK-Key': config.apiKey
  };
}

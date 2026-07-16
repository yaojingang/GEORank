export const DEVICE_ID_STORAGE_KEY = 'georank_device_id_v1';

function createDeviceId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `device-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

export function getOrCreateDeviceId() {
  if (typeof window === 'undefined') return '';
  const stored = window.localStorage.getItem(DEVICE_ID_STORAGE_KEY)?.trim();
  if (stored && stored.length >= 16) return stored;
  const deviceId = createDeviceId();
  window.localStorage.setItem(DEVICE_ID_STORAGE_KEY, deviceId);
  return deviceId;
}

export function getDeviceHeaders(): Record<string, string> {
  const deviceId = getOrCreateDeviceId();
  return deviceId ? {'X-GEOrank-Device-ID': deviceId} : {};
}

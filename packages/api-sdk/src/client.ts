const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export function createBrowserApiClient() {
  return {
    async get<T>(path: string): Promise<T> {
      const response = await fetch(`${API_BASE}${path}`, {credentials: 'include'});
      if (!response.ok) {
        throw new Error(`API ${response.status}`);
      }
      return response.json();
    }
  };
}

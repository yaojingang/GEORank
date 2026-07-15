const API_BASE = process.env.API_BASE || 'http://localhost:8000';

export function createServerApiClient() {
  return {
    async get<T>(path: string): Promise<T> {
      const response = await fetch(`${API_BASE}${path}`, {cache: 'no-store'});
      if (!response.ok) {
        throw new Error(`API ${response.status}`);
      }
      return response.json();
    }
  };
}

export type ApiErrorDetail = {
  code?: string;
  message?: string;
  guidance?: Record<string, unknown>;
  quota?: Record<string, unknown>;
};

export class ApiRequestError extends Error {
  status: number;
  code?: string;
  guidance?: Record<string, unknown>;
  quota?: Record<string, unknown>;

  constructor(status: number, detail?: string | ApiErrorDetail) {
    const structured = detail && typeof detail === 'object' ? detail : undefined;
    super(typeof detail === 'string' ? detail : structured?.message || `API ${status}`);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = structured?.code;
    this.guidance = structured?.guidance;
    this.quota = structured?.quota;
  }
}

export async function parseApiResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({})) as {detail?: string | ApiErrorDetail};
  if (!response.ok) throw new ApiRequestError(response.status, payload.detail);
  return payload as T;
}

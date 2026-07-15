const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export type DiagnoseRequest = {
  url: string;
  company_id?: string;
};

export type DiagnoseResponse = {
  report_id: string;
  status: string;
};

export type DiagnosticHistoryItem = {
  report_id: string;
  url: string;
  status: string;
  overall_score?: number | null;
  created_at: string;
};

export type DiagnosticReportResponse = {
  report_id: string;
  url: string;
  company_id?: string | null;
  status: string;
  overall_score?: number | null;
  schema_analysis?: Record<string, unknown> | null;
  content_analysis?: Record<string, unknown> | null;
  meta_analysis?: Record<string, unknown> | null;
  citation_analysis?: Record<string, unknown> | null;
  recommendations?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
};

async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail || `API ${response.status}`);
  }
  return payload as T;
}

export async function startDiagnosis(token: string, body: DiagnoseRequest): Promise<DiagnoseResponse> {
  const response = await fetch(`${API_BASE}/api/diagnostics/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(body)
  });
  return parseJson<DiagnoseResponse>(response);
}

export async function listDiagnosticHistory(
  token: string,
  page = 1,
  size = 20
): Promise<DiagnosticHistoryItem[]> {
  const search = new URLSearchParams({
    page: String(page),
    size: String(size)
  });
  const response = await fetch(`${API_BASE}/api/diagnostics/history?${search.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: 'no-store'
  });
  return parseJson<DiagnosticHistoryItem[]>(response);
}

export async function getDiagnosticReport(
  token: string,
  reportId: string
): Promise<DiagnosticReportResponse> {
  const response = await fetch(`${API_BASE}/api/diagnostics/${encodeURIComponent(reportId)}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: 'no-store'
  });
  return parseJson<DiagnosticReportResponse>(response);
}

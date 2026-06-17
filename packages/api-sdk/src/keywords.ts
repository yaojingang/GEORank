const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export type KeywordExpandRequest = {
  seeds: string[];
};

export type KeywordProfile = {
  name: string;
  company_hint: string;
  business_model: string;
  target_users: string[];
  keyword_strategy: string;
};

export type KeywordDimensionItem = {
  keyword: string;
  recommendation_score: number;
  business_score: number;
  reason?: string | null;
};

export type KeywordDimension = {
  key: string;
  name: string;
  icon: string;
  description: string;
  count: number;
  items: KeywordDimensionItem[];
};

export type KeywordSummary = {
  total_keywords: number;
  average_recommendation_score: number;
  average_business_score: number;
  high_recommendation_ratio: number;
  high_business_ratio: number;
};

export type KeywordExpandResponse = {
  seeds: string[];
  profile: KeywordProfile;
  dimensions: KeywordDimension[];
  summary: KeywordSummary;
};

async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail || `API ${response.status}`);
  }
  return payload as T;
}

export async function expandKeywords(
  body: KeywordExpandRequest,
  token?: string
): Promise<KeywordExpandResponse> {
  const response = await fetch(`${API_BASE}/api/keywords/expand`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(body)
  });
  return parseJson<KeywordExpandResponse>(response);
}

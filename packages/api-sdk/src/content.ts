export type TutorialNavItem = {
  title: string;
  slug: string;
  path_key: string;
  reading_time_minutes?: number | null;
};

export type TutorialNavGroup = {
  category: string;
  items: TutorialNavItem[];
};

export type TutorialDetail = {
  id: string;
  title: string;
  slug: string;
  path_key: string;
  content_type: string;
  status: string;
  markdown_body?: string | null;
  html_body?: string | null;
  cover_image?: string | null;
  reading_time_minutes?: number | null;
  tags?: string[];
  view_count?: number;
  created_at?: string;
  updated_at?: string | null;
};

export type ContentSummary = {
  id: string;
  title: string;
  slug: string;
  path_key: string;
  content_type: string;
  cover_image?: string | null;
  reading_time_minutes?: number | null;
  tags?: string[];
  view_count?: number;
  created_at?: string;
  updated_at?: string | null;
};

const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`API ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getTutorialNav(): Promise<TutorialNavGroup[]> {
  const response = await fetch(`${API_BASE}/api/content/nav`, {cache: 'no-store'});
  return parseJson<TutorialNavGroup[]>(response);
}

export async function listContent({
  contentType,
  tag,
  page = 1,
  size = 20
}: {
  contentType?: string;
  tag?: string;
  page?: number;
  size?: number;
} = {}): Promise<ContentSummary[]> {
  const searchParams = new URLSearchParams({
    page: String(page),
    size: String(size)
  });

  if (contentType) searchParams.set('content_type', contentType);
  if (tag) searchParams.set('tag', tag);

  const response = await fetch(`${API_BASE}/api/content/?${searchParams.toString()}`, {
    cache: 'no-store'
  });
  return parseJson<ContentSummary[]>(response);
}

export async function getTutorialDetail(identifier: string): Promise<TutorialDetail> {
  const response = await fetch(`${API_BASE}/api/content/resolve/${encodeURIComponent(identifier)}`, {
    cache: 'no-store'
  });
  return parseJson<TutorialDetail>(response);
}

export async function getTutorialBySlug(slug: string): Promise<TutorialDetail> {
  const response = await fetch(`${API_BASE}/api/content/${encodeURIComponent(slug)}`, {
    cache: 'no-store'
  });
  return parseJson<TutorialDetail>(response);
}

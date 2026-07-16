import type { CompanyDetail, PaginatedCompanies, SimilarCompanyItem } from './generated/types.gen';
export type { CompanyBrief, CompanyDetail, PaginatedCompanies, SimilarCompanyItem } from './generated/types.gen';

const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`API ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function listCompanies(): Promise<PaginatedCompanies> {
  const response = await fetch(`${API_BASE}/api/companies/`, {cache: 'no-store'});
  return parseJson<PaginatedCompanies>(response);
}

export async function listCompaniesWithParams({
  page = 1,
  size = 20,
  sort = 'newest',
  category,
  q
}: {
  page?: number;
  size?: number;
  sort?: 'newest' | 'geo_score' | 'views' | 'upvotes';
  category?: string;
  q?: string;
} = {}): Promise<PaginatedCompanies> {
  const searchParams = new URLSearchParams({
    page: String(page),
    size: String(size),
    sort
  });

  if (category) searchParams.set('category', category);
  if (q) searchParams.set('q', q);

  const response = await fetch(`${API_BASE}/api/companies/?${searchParams.toString()}`, {
    cache: 'no-store'
  });
  return parseJson<PaginatedCompanies>(response);
}

export async function getCompanyDetail(identifier: string): Promise<CompanyDetail> {
  const response = await fetch(`${API_BASE}/api/companies/${encodeURIComponent(identifier)}`, {
    cache: 'no-store'
  });
  return parseJson<CompanyDetail>(response);
}

export async function getSimilarCompanies(identifier: string): Promise<SimilarCompanyItem[]> {
  const response = await fetch(`${API_BASE}/api/companies/${encodeURIComponent(identifier)}/similar`, {
    cache: 'no-store'
  });
  return parseJson<SimilarCompanyItem[]>(response);
}

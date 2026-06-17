const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export type AdminDashboardResponse = {
  total_companies: number;
  total_solutions: number;
  total_users: number;
  total_diagnostics: number;
  total_contents: number;
  user_stats: {
    total: number;
    active: number;
    admin: number;
    new_today: number;
  };
  pipeline_stats: Record<string, number>;
  failure_stats: {
    failed_companies: number;
    failed_diagnostics: number;
  };
  geo_distribution: Record<string, number>;
};

export type AdminRecentFailureItem = {
  id: string;
  name?: string;
  url: string;
  status?: string;
  pipeline_status?: string;
  error_message?: string | null;
  pipeline_error?: string | null;
  created_at: string;
  updated_at?: string;
};

export type AdminRecentFailuresResponse = {
  companies: AdminRecentFailureItem[];
  diagnostics: AdminRecentFailureItem[];
  limit: number;
};

export type AdminCompanySummary = {
  id: string;
  name: string;
  url: string;
  short_description?: string | null;
  category?: string | null;
  is_geo_certified: boolean;
  pipeline_status: string;
  pipeline_error?: string | null;
  publish_status: string;
  geo_score?: number | null;
  upvotes: number;
  created_at: string;
  updated_at: string;
};

export type AdminCompanyListResponse = {
  items: AdminCompanySummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

export type AdminCompanyDetail = {
  id: string;
  name: string;
  url: string;
  logo_url?: string | null;
  description?: string | null;
  short_description?: string | null;
  category?: string | null;
  tags: string[];
  is_geo_certified: boolean;
  founded_date?: string | null;
  headquarters?: string | null;
  employee_count?: string | null;
  funding_stage?: string | null;
  tech_level?: string | null;
  tech_stack: string[];
  team_members: Array<Record<string, unknown>>;
  geo_score?: number | null;
  geo_details?: Record<string, number | null>;
  pipeline_status: string;
  pipeline_error?: string | null;
  publish_status: string;
  screenshots: string[];
  upvotes: number;
  submitted_by?: string | null;
  submitted_by_user?: {
    id: string;
    username: string;
    email: string;
  } | null;
  diagnostic_report_count: number;
  latest_diagnostic?: {
    id: string;
    url: string;
    status: string;
    overall_score?: number | null;
    created_at: string;
  } | null;
  related_solutions?: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type AdminCompanyListParams = {
  page?: number;
  size?: number;
  publishStatus?: string;
  pipelineStatus?: string;
  category?: string;
  search?: string;
  sort?: string;
};

export type AdminSolutionConversationSummary = {
  id: string;
  title: string;
  user_id?: string | null;
  is_public: boolean;
  username?: string | null;
  user_email?: string | null;
  message_count: number;
  assistant_message_count: number;
  has_recommendations: boolean;
  recommendation_company_count: number;
  diagnostic_context_ids: string[];
  diagnostic_context_count: number;
  latest_message_excerpt: string;
  last_assistant_message_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminSolutionConversationListResponse = {
  items: AdminSolutionConversationSummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
  summary: {
    message_count: number;
    assistant_message_count: number;
    conversations_with_recommendations: number;
    conversations_with_diagnostics: number;
    public_conversation_count: number;
    owned_conversation_count: number;
    average_message_count: number;
  };
};

export type AdminSolutionConversationDetail = {
  id: string;
  title: string;
  user_id?: string | null;
  is_public: boolean;
  visibility: 'public' | 'owned';
  username?: string | null;
  user_email?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  assistant_message_count: number;
  diagnostic_context_count: number;
  recommended_company_count: number;
  first_message_at?: string | null;
  last_user_message_at?: string | null;
  last_assistant_message_at?: string | null;
  messages: Array<{
    id: string;
    role: string;
    content: string;
    recommended_companies: Array<Record<string, unknown>>;
    diagnostic_context_id?: string | null;
    diagnostic_context?: {
      report_id: string;
      url: string;
      status: string;
      overall_score?: number | null;
    } | null;
    created_at: string;
  }>;
};

export type AdminSolutionTemplates = {
  system_prompt: string;
  response_instruction: string;
  streaming_system_prompt: string;
  uses_default: boolean;
  updated_at?: string | null;
  updated_by_username?: string | null;
  customized_fields: string[];
  customized_field_count: number;
  template_field_total: number;
  field_sources: Record<string, 'custom' | 'default'>;
};

export type AdminSolutionListParams = {
  page?: number;
  size?: number;
  search?: string;
  visibility?: 'public' | 'owned';
  linkage?: 'recommendations' | 'diagnostics';
};

export type AdminDiagnosticReportSummary = {
  id: string;
  url: string;
  status: string;
  overall_score?: number | null;
  company_id?: string | null;
  company_name?: string | null;
  user_id?: string | null;
  username?: string | null;
  user_email?: string | null;
  error_message?: string | null;
  created_at: string;
};

export type AdminDiagnosticReportListResponse = {
  items: AdminDiagnosticReportSummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
  summary: {
    completed_count: number;
    failed_count: number;
    average_score?: number | null;
  };
};

export type AdminDiagnosticAnalysis = {
  score?: number | null;
  summary?: string | null;
  strengths?: string[];
  issues?: string[];
  [key: string]: unknown;
};

export type AdminDiagnosticRecommendations = Record<string, Array<string | Record<string, unknown>>>;

export type AdminDiagnosticReportDetail = {
  id: string;
  url: string;
  status: string;
  overall_score?: number | null;
  company_id?: string | null;
  company_name?: string | null;
  user_id?: string | null;
  username?: string | null;
  user_email?: string | null;
  schema_analysis: AdminDiagnosticAnalysis;
  content_analysis: AdminDiagnosticAnalysis;
  meta_analysis: AdminDiagnosticAnalysis;
  citation_analysis: AdminDiagnosticAnalysis;
  recommendations: AdminDiagnosticRecommendations;
  error_message?: string | null;
  raw_html_key?: string | null;
  created_at: string;
  rule_config: {
    weights: {
      schema: number;
      content: number;
      meta: number;
      citation: number;
    };
  };
  related_solutions: Array<{
    id: string;
    title: string;
    username?: string | null;
    user_email?: string | null;
    updated_at: string;
    latest_message_excerpt: string;
    match_types: string[];
  }>;
};

export type AdminDiagnosticRules = {
  weights: {
    schema: number;
    content: number;
    meta: number;
    citation: number;
  };
};

export type AdminDiagnosticListParams = {
  page?: number;
  size?: number;
  statusFilter?: string;
  search?: string;
};

export type AdminTutorialSummary = {
  id: string;
  title: string;
  slug: string;
  path_key?: string | null;
  content_type: string;
  status: string;
  view_count: number;
  reading_time_minutes?: number | null;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type AdminTutorialListResponse = {
  items: AdminTutorialSummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
  summary: {
    tutorial_total: number;
    tutorial_published: number;
    draft_assets: number;
    template_total: number;
    total_views: number;
  };
};

export type AdminTutorialDetail = {
  id: string;
  title: string;
  slug: string;
  path_key?: string | null;
  content_type: string;
  status: string;
  markdown_body: string;
  html_body: string;
  cover_image?: string | null;
  tags: string[];
  reading_time_minutes?: number | null;
  view_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminTutorialPayload = {
  title: string;
  content_type: string;
  markdown_body: string;
  status?: string | null;
  cover_image?: string | null;
  tags: string[];
  reading_time_minutes?: number | null;
};

export type AdminTutorialListParams = {
  page?: number;
  size?: number;
  contentType?: string;
  statusFilter?: string;
  search?: string;
};

export type AdminUserSummary = {
  id: string;
  email: string;
  username: string;
  phone?: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
};

export type AdminUserListResponse = {
  items: AdminUserSummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

export type AdminUserListParams = {
  page?: number;
  size?: number;
  role?: string;
  isActive?: boolean;
  search?: string;
};

export type AdminSettingsItem = {
  value: string | number | boolean | string[] | Record<string, unknown> | null;
  category: string;
  is_public: boolean;
  updated_at?: string | null;
};

export type AdminSettingsResponse = Record<string, AdminSettingsItem>;

export type AdminSettingsUpdatePayload = Record<
  string,
  {
    value: string | number | boolean | string[] | Record<string, unknown> | null;
    category?: string;
    is_public?: boolean;
  }
>;

function authHeaders(token: string, headers?: HeadersInit): HeadersInit {
  return {
    ...(headers || {}),
    Authorization: `Bearer ${token}`
  };
}

async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as {detail?: string}).detail || `API ${response.status}`);
  }
  return payload as T;
}

export async function getAdminDashboard(token: string): Promise<AdminDashboardResponse> {
  const response = await fetch(`${API_BASE}/api/admin/dashboard`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminDashboardResponse>(response);
}

export async function getAdminRecentFailures(
  token: string,
  limit = 8
): Promise<AdminRecentFailuresResponse> {
  const response = await fetch(`${API_BASE}/api/admin/ops/recent-failures?limit=${limit}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminRecentFailuresResponse>(response);
}

export async function listAdminCompanies(
  token: string,
  params: AdminCompanyListParams = {}
): Promise<AdminCompanyListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });

  if (params.publishStatus) searchParams.set('publish_status', params.publishStatus);
  if (params.pipelineStatus) searchParams.set('pipeline_status', params.pipelineStatus);
  if (params.category) searchParams.set('category', params.category);
  if (params.search) searchParams.set('search', params.search);
  if (params.sort) searchParams.set('sort', params.sort);

  const response = await fetch(`${API_BASE}/api/admin/companies?${searchParams.toString()}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminCompanyListResponse>(response);
}

export async function getAdminCompanyDetail(
  token: string,
  companyId: string
): Promise<AdminCompanyDetail> {
  const response = await fetch(`${API_BASE}/api/admin/companies/${encodeURIComponent(companyId)}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminCompanyDetail>(response);
}

export async function approveAdminCompany(token: string, companyId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/companies/${encodeURIComponent(companyId)}/approve`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string; company_id: string}>(response);
}

export async function rejectAdminCompany(token: string, companyId: string, reason = '') {
  const url = new URL(
    `${API_BASE}/api/admin/companies/${encodeURIComponent(companyId)}/reject`
  );
  if (reason) {
    url.searchParams.set('reason', reason);
  }
  const response = await fetch(url.toString(), {
    method: 'POST',
    headers: authHeaders(token)
  });
  return parseJson<{status: string; company_id: string}>(response);
}

export async function retryAdminCompanyPipeline(token: string, companyId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/companies/${encodeURIComponent(companyId)}/retry-pipeline`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string; company_id: string}>(response);
}

export async function deleteAdminCompany(token: string, companyId: string) {
  const response = await fetch(`${API_BASE}/api/admin/companies/${encodeURIComponent(companyId)}`, {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  return parseJson<{status: string; company_id: string}>(response);
}

export async function listAdminSolutionConversations(
  token: string,
  params: AdminSolutionListParams = {}
): Promise<AdminSolutionConversationListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });

  if (params.search) searchParams.set('search', params.search);
  if (params.visibility) searchParams.set('visibility', params.visibility);
  if (params.linkage) searchParams.set('linkage', params.linkage);

  const response = await fetch(
    `${API_BASE}/api/admin/solutions/conversations?${searchParams.toString()}`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  return parseJson<AdminSolutionConversationListResponse>(response);
}

export async function getAdminSolutionConversation(
  token: string,
  conversationId: string
): Promise<AdminSolutionConversationDetail> {
  const response = await fetch(
    `${API_BASE}/api/admin/solutions/conversations/${encodeURIComponent(conversationId)}`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  return parseJson<AdminSolutionConversationDetail>(response);
}

export async function deleteAdminSolutionConversation(token: string, conversationId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/solutions/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: 'DELETE',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string; conversation_id: string}>(response);
}

export async function getAdminSolutionTemplates(token: string): Promise<AdminSolutionTemplates> {
  const response = await fetch(`${API_BASE}/api/admin/solutions/templates`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminSolutionTemplates>(response);
}

export async function updateAdminSolutionTemplates(
  token: string,
  payload: Pick<
    AdminSolutionTemplates,
    'system_prompt' | 'response_instruction' | 'streaming_system_prompt'
  >
): Promise<AdminSolutionTemplates> {
  const response = await fetch(`${API_BASE}/api/admin/solutions/templates`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminSolutionTemplates>(response);
}

export async function resetAdminSolutionTemplates(token: string): Promise<AdminSolutionTemplates> {
  const response = await fetch(`${API_BASE}/api/admin/solutions/templates/reset`, {
    method: 'POST',
    headers: authHeaders(token)
  });
  return parseJson<AdminSolutionTemplates>(response);
}

export async function listAdminDiagnosticReports(
  token: string,
  params: AdminDiagnosticListParams = {}
): Promise<AdminDiagnosticReportListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });

  if (params.search) searchParams.set('search', params.search);
  if (params.statusFilter) searchParams.set('status_filter', params.statusFilter);

  const response = await fetch(
    `${API_BASE}/api/admin/diagnostics/reports?${searchParams.toString()}`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  return parseJson<AdminDiagnosticReportListResponse>(response);
}

export async function getAdminDiagnosticReport(
  token: string,
  reportId: string
): Promise<AdminDiagnosticReportDetail> {
  const response = await fetch(
    `${API_BASE}/api/admin/diagnostics/reports/${encodeURIComponent(reportId)}`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  return parseJson<AdminDiagnosticReportDetail>(response);
}

export async function retryAdminDiagnosticReport(token: string, reportId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/diagnostics/reports/${encodeURIComponent(reportId)}/retry`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string; report_id: string}>(response);
}

export async function getAdminDiagnosticRules(token: string): Promise<AdminDiagnosticRules> {
  const response = await fetch(`${API_BASE}/api/admin/diagnostics/rules`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminDiagnosticRules>(response);
}

export async function updateAdminDiagnosticRules(
  token: string,
  weights: {schema: number; content: number; meta: number; citation: number}
): Promise<AdminDiagnosticRules> {
  const response = await fetch(`${API_BASE}/api/admin/diagnostics/rules`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(weights)
  });
  return parseJson<AdminDiagnosticRules>(response);
}

export async function listAdminTutorials(
  token: string,
  params: AdminTutorialListParams = {}
): Promise<AdminTutorialListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });

  if (params.contentType) searchParams.set('content_type', params.contentType);
  if (params.statusFilter) searchParams.set('status_filter', params.statusFilter);
  if (params.search) searchParams.set('search', params.search);

  const response = await fetch(`${API_BASE}/api/admin/tutorials?${searchParams.toString()}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminTutorialListResponse>(response);
}

export async function getAdminTutorial(
  token: string,
  contentId: string
): Promise<AdminTutorialDetail> {
  const response = await fetch(`${API_BASE}/api/admin/tutorials/${encodeURIComponent(contentId)}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminTutorialDetail>(response);
}

export async function createAdminTutorial(
  token: string,
  payload: AdminTutorialPayload
): Promise<{id: string; slug: string; path_key?: string | null}> {
  const response = await fetch(`${API_BASE}/api/admin/tutorials`, {
    method: 'POST',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<{id: string; slug: string; path_key?: string | null}>(response);
}

export async function updateAdminTutorial(
  token: string,
  contentId: string,
  payload: AdminTutorialPayload
): Promise<{id: string; status: string}> {
  const response = await fetch(`${API_BASE}/api/admin/tutorials/${encodeURIComponent(contentId)}`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<{id: string; status: string}>(response);
}

export async function publishAdminTutorial(token: string, contentId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/tutorials/${encodeURIComponent(contentId)}/publish`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string}>(response);
}

export async function deleteAdminTutorial(token: string, contentId: string) {
  const response = await fetch(`${API_BASE}/api/admin/tutorials/${encodeURIComponent(contentId)}`, {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  return parseJson<Record<string, never>>(response);
}

export async function listAdminUsers(
  token: string,
  params: AdminUserListParams = {}
): Promise<AdminUserListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });

  if (params.role) searchParams.set('role', params.role);
  if (typeof params.isActive === 'boolean') searchParams.set('is_active', String(params.isActive));
  if (params.search) searchParams.set('search', params.search);

  const response = await fetch(`${API_BASE}/api/admin/users?${searchParams.toString()}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminUserListResponse>(response);
}

export async function toggleAdminUserActive(token: string, userId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/toggle-active`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<{user_id: string; is_active: boolean}>(response);
}

export async function updateAdminUserRole(token: string, userId: string, role: string) {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/role`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify({role})
  });
  return parseJson<{user_id: string; role: string}>(response);
}

export async function getAdminSettings(token: string): Promise<AdminSettingsResponse> {
  const response = await fetch(`${API_BASE}/api/admin/settings`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminSettingsResponse>(response);
}

export async function updateAdminSettings(
  token: string,
  payload: AdminSettingsUpdatePayload
): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/admin/settings`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<Record<string, unknown>>(response);
}

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
  path_key?: string | null;
  preview_url?: string;
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
  path_key?: string | null;
  preview_url: string;
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

export type AdminCompanyPayload = {
  name?: string;
  url?: string;
  logo_url?: string | null;
  description?: string | null;
  short_description?: string | null;
  category?: string | null;
  tags?: string[];
  is_geo_certified?: boolean;
  founded_date?: string | null;
  headquarters?: string | null;
  employee_count?: string | null;
  funding_stage?: string | null;
  tech_level?: string | null;
  tech_stack?: string[];
  geo_score?: number | null;
  publish_status?: string | null;
  pipeline_status?: string | null;
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

export type AdminExpert = {
  id: string;
  slug?: string | null;
  display_name: string;
  avatar_initials?: string | null;
  title: string;
  category: string;
  specialty_label: string;
  summary: string;
  expertise: string[];
  consultation: string;
  keywords: string[];
  sort_order: number;
  is_featured: boolean;
  is_published: boolean;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AdminExpertPayload = Omit<
  AdminExpert,
  'id' | 'created_by' | 'created_at' | 'updated_at'
>;

export type AdminExpertListParams = {
  page?: number;
  size?: number;
  category?: string;
  statusFilter?: string;
  search?: string;
};

export type AdminExpertListResponse = {
  items: AdminExpert[];
  total: number;
  page: number;
  size: number;
  pages: number;
  summary: {
    total: number;
    published: number;
    draft: number;
    featured: number;
    category_counts: Array<{category: string; count: number}>;
  };
};

export type AdminKeywordPackSummary = {
  id: string;
  title: string;
  seed_keywords: string[];
  source_type: string;
  source_ref_id?: string | null;
  status: string;
  summary?: string | null;
  dimension_count: number;
  total_keywords: number;
  avg_recommendation_score?: number | null;
  avg_business_score?: number | null;
  high_recommendation_ratio?: number | null;
  high_business_ratio?: number | null;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AdminKeywordPackDetail = AdminKeywordPackSummary & {
  profile: Record<string, unknown>;
  dimensions: Array<{
    key: string;
    name: string;
    icon?: string | null;
    description?: string | null;
    count: number;
    items: Array<{
      id: string;
      keyword: string;
      recommendation_score: number;
      business_score: number;
      intent_label?: string | null;
      source: string;
      is_selected: boolean;
      reason?: string | null;
    }>;
  }>;
};

export type AdminKeywordPackListParams = {
  page?: number;
  size?: number;
  search?: string;
  sourceType?: string;
};

export type AdminKeywordPackListResponse = {
  items: AdminKeywordPackSummary[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

export type AdminKeywordSummary = {
  total_packs: number;
  completed_packs: number;
  total_keywords: number;
  avg_recommendation_score: number;
  avg_business_score: number;
  latest_pack?: AdminKeywordPackSummary | null;
  source_counts: Array<{source_type: string; count: number}>;
  dimension_counts: Array<{key: string; name: string; count: number}>;
};

export type AdminKeywordPackCreatePayload = {
  title?: string;
  seeds: string[];
  source_type?: string;
  source_ref_id?: string | null;
};

export type AdminSolutionChannel = {
  key: string;
  name: string;
  description: string;
  icon: string;
  enabled: boolean;
  system_hint: string;
  sample_questions: string[];
};

export type AdminSolutionChannels = {
  default_channel_key: string;
  channels: AdminSolutionChannel[];
  channel_count: number;
  enabled_channel_count: number;
  uses_default: boolean;
  updated_at?: string | null;
  updated_by_username?: string | null;
};

export type AdminByokGuidance = {
  provider: string;
  title: string;
  message: string;
  cta_label: string;
  official_url: string;
  base_url: string;
  model: string;
};

export type AdminApiPolicy = {
  access_mode: string;
  daily_token_limit: number;
  lifetime_token_grant: number;
  global_daily_token_limit: number;
  global_budget_enabled: boolean;
  emergency_byok_only: boolean;
  quota_reset_timezone: string;
  allow_anonymous_ai_usage: boolean;
  allow_user_byok: boolean;
  byok_transport_mode: string;
  byok_guidance: AdminByokGuidance;
  allowed_byok_providers: Array<{
    key: string;
    name: string;
    base_url: string;
    default_model: string;
  }>;
  metered_modules: string[];
};

export type AdminGlobalBudgetSummary = {
  enabled: boolean;
  emergency_byok_only: boolean;
  usage_date: string;
  limit_tokens: number;
  used_tokens: number;
  reserved_tokens: number;
  remaining_tokens: number;
  state: string;
};

export type AdminApiPolicyResponse = {
  policy: AdminApiPolicy;
  summary: Record<string, unknown> & {global_budget?: AdminGlobalBudgetSummary};
};

export type AdminLLMProvider = {
  id?: string | null;
  name: string;
  base_url: string;
  model: string;
  api_key?: string | null;
  enabled: boolean;
  priority: number;
  has_api_key?: boolean;
};

export type AdminLLMProviders = {
  strategy: string;
  providers: AdminLLMProvider[];
  provider_count: number;
  enabled_provider_count: number;
  updated_at?: string | null;
};

export type AdminLLMProviderTestResponse = {
  ok: boolean;
  provider_id: string;
  status_code?: number;
  latency_ms?: number;
  message: string;
  detail?: string;
  content_preview?: string;
  tested_at: string;
};

export type AdminFrontendModule = {
  key: string;
  name?: string;
  path?: string;
  description?: string;
  enabled: boolean;
  protected_paths?: string[];
  is_default?: boolean;
};

export type AdminFrontendModules = {
  default_module: string;
  modules: AdminFrontendModule[];
  module_count: number;
  enabled_module_count: number;
  updated_at?: string | null;
  updated_by_username?: string | null;
};

export type AdminHomepageRelease = {
  id: string;
  title: string;
  is_builtin: boolean;
  source_type: string;
  status: string;
  entry_path?: string | null;
  storage_path?: string | null;
  file_count?: number | null;
  compressed_size?: number | null;
  extracted_size?: number | null;
  sha256?: string | null;
  manifest: Record<string, unknown>;
  error_message?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  activated_at?: string | null;
  preview_url: string;
};

export type AdminHomepageResponse = {
  runtime: Record<string, unknown>;
  releases: AdminHomepageRelease[];
};

export type AdminHomepageSource = {
  release_id: string;
  html: string;
  sha256: string;
};

export type AdminHomepageUpdateResponse = {
  release: AdminHomepageRelease;
  updated_active: boolean;
  source_sha256: string;
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

export type AdminUserQuota = {
  user_id: string;
  username: string;
  role: string;
  principal_id: string;
  granted_tokens: number;
  consumed_tokens: number;
  reserved_tokens: number;
  remaining_tokens: number;
  request_count: number;
  frozen: boolean;
  linked_user_count: number;
  linked_device_count: number;
  updated_at?: string | null;
};

export type AdminUserQuotaUpdatePayload = {
  granted_tokens?: number;
  consumed_tokens?: number;
  frozen?: boolean;
  reason: string;
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

export type AdminUserCreatePayload = {
  email: string;
  username: string;
  password: string;
  role?: string;
  phone?: string | null;
};

export type AdminUserUpdatePayload = {
  email?: string;
  username?: string;
  phone?: string | null;
  role?: string;
  is_active?: boolean;
  is_verified?: boolean;
};

export type AdminUserPasswordPayload = {
  password: string;
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
    const detail = (payload as {
      detail?: string | {
        message?: string;
        missing_fields?: string[];
        pipeline_status?: string;
        pipeline_error?: string | null;
      };
    }).detail;
    if (typeof detail === 'string') {
      throw new Error(detail);
    }
    if (detail && typeof detail === 'object') {
      const labels: Record<string, string> = {
        description: '公司介绍',
        category: '业务分类',
        tags: '业务标签',
        geo_score: 'GEO 评分',
        geo_details: 'GEO 四维明细'
      };
      const missing = (detail.missing_fields || []).map((field) => labels[field] || field);
      const pipelineProblem = String(detail.pipeline_error || '').trim();
      const suffix = missing.length
        ? `（缺失：${missing.join('、')}）`
        : pipelineProblem
          ? `（${pipelineProblem}）`
          : detail.pipeline_status
            ? `（当前状态：${detail.pipeline_status}）`
            : '';
      throw new Error(`${detail.message || `API ${response.status}`}${suffix}`);
    }
    throw new Error(`API ${response.status}`);
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

export async function createAdminCompany(
  token: string,
  payload: AdminCompanyPayload
): Promise<AdminCompanyDetail> {
  const response = await fetch(`${API_BASE}/api/admin/companies`, {
    method: 'POST',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminCompanyDetail>(response);
}

export async function updateAdminCompany(
  token: string,
  companyId: string,
  payload: AdminCompanyPayload
): Promise<AdminCompanyDetail> {
  const response = await fetch(`${API_BASE}/api/admin/companies/${encodeURIComponent(companyId)}`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
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

export async function getAdminSolutionChannels(token: string): Promise<AdminSolutionChannels> {
  const response = await fetch(`${API_BASE}/api/admin/solutions/channels`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminSolutionChannels>(response);
}

export async function updateAdminSolutionChannels(
  token: string,
  payload: Pick<AdminSolutionChannels, 'default_channel_key' | 'channels'>
): Promise<AdminSolutionChannels> {
  const response = await fetch(`${API_BASE}/api/admin/solutions/channels`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminSolutionChannels>(response);
}

export async function resetAdminSolutionChannels(token: string): Promise<AdminSolutionChannels> {
  const response = await fetch(`${API_BASE}/api/admin/solutions/channels/reset`, {
    method: 'POST',
    headers: authHeaders(token)
  });
  return parseJson<AdminSolutionChannels>(response);
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

export async function deleteAdminDiagnosticReport(token: string, reportId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/diagnostics/reports/${encodeURIComponent(reportId)}`,
    {
      method: 'DELETE',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string; report_id: string}>(response);
}

export async function exportAdminDiagnosticReport(
  token: string,
  reportId: string,
  format: 'markdown' | 'json'
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE}/api/admin/diagnostics/reports/${encodeURIComponent(reportId)}/export?format=${format}`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error((payload as {detail?: string}).detail || `API ${response.status}`);
  }
  return response.blob();
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

export async function listAdminExperts(
  token: string,
  params: AdminExpertListParams = {}
): Promise<AdminExpertListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });
  if (params.category) searchParams.set('category', params.category);
  if (params.statusFilter) searchParams.set('status_filter', params.statusFilter);
  if (params.search) searchParams.set('search', params.search);
  const response = await fetch(`${API_BASE}/api/admin/experts?${searchParams.toString()}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminExpertListResponse>(response);
}

export async function getAdminExpert(token: string, expertId: string): Promise<AdminExpert> {
  const response = await fetch(`${API_BASE}/api/admin/experts/${encodeURIComponent(expertId)}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminExpert>(response);
}

export async function createAdminExpert(
  token: string,
  payload: AdminExpertPayload
): Promise<AdminExpert> {
  const response = await fetch(`${API_BASE}/api/admin/experts`, {
    method: 'POST',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminExpert>(response);
}

export async function updateAdminExpert(
  token: string,
  expertId: string,
  payload: AdminExpertPayload
): Promise<AdminExpert> {
  const response = await fetch(`${API_BASE}/api/admin/experts/${encodeURIComponent(expertId)}`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminExpert>(response);
}

export async function deleteAdminExpert(token: string, expertId: string) {
  const response = await fetch(`${API_BASE}/api/admin/experts/${encodeURIComponent(expertId)}`, {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error((payload as {detail?: string}).detail || `API ${response.status}`);
  }
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

export async function getAdminUser(token: string, userId: string): Promise<AdminUserSummary> {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminUserSummary>(response);
}

export async function getAdminUserQuota(token: string, userId: string): Promise<AdminUserQuota> {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/ai-quota`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminUserQuota>(response);
}

export async function updateAdminUserQuota(
  token: string,
  userId: string,
  payload: AdminUserQuotaUpdatePayload
): Promise<AdminUserQuota> {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/ai-quota`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminUserQuota>(response);
}

export async function createAdminUser(
  token: string,
  payload: AdminUserCreatePayload
): Promise<AdminUserSummary> {
  const response = await fetch(`${API_BASE}/api/admin/users`, {
    method: 'POST',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminUserSummary>(response);
}

export async function updateAdminUser(
  token: string,
  userId: string,
  payload: AdminUserUpdatePayload
): Promise<AdminUserSummary> {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminUserSummary>(response);
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

export async function resetAdminUserPassword(
  token: string,
  userId: string,
  payload: AdminUserPasswordPayload
) {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}/password`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<{user_id: string; message: string}>(response);
}

export async function deleteAdminUser(token: string, userId: string) {
  const response = await fetch(`${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  return parseJson<{status: string; user_id: string}>(response);
}

export async function getAdminKeywordSummary(token: string): Promise<AdminKeywordSummary> {
  const response = await fetch(`${API_BASE}/api/admin/keywords/summary`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminKeywordSummary>(response);
}

export async function listAdminKeywordPacks(
  token: string,
  params: AdminKeywordPackListParams = {}
): Promise<AdminKeywordPackListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    size: String(params.size ?? 20)
  });
  if (params.search) searchParams.set('search', params.search);
  if (params.sourceType) searchParams.set('source_type', params.sourceType);
  const response = await fetch(`${API_BASE}/api/admin/keywords/packs?${searchParams.toString()}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminKeywordPackListResponse>(response);
}

export async function createAdminKeywordPack(
  token: string,
  payload: AdminKeywordPackCreatePayload
): Promise<AdminKeywordPackDetail> {
  const response = await fetch(`${API_BASE}/api/admin/keywords/packs`, {
    method: 'POST',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminKeywordPackDetail>(response);
}

export async function getAdminKeywordPack(
  token: string,
  packId: string
): Promise<AdminKeywordPackDetail> {
  const response = await fetch(`${API_BASE}/api/admin/keywords/packs/${encodeURIComponent(packId)}`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminKeywordPackDetail>(response);
}

export async function exportAdminKeywordPack(token: string, packId: string): Promise<Blob> {
  const response = await fetch(
    `${API_BASE}/api/admin/keywords/packs/${encodeURIComponent(packId)}/export`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error((payload as {detail?: string}).detail || `API ${response.status}`);
  }
  return response.blob();
}

export async function deleteAdminKeywordPack(token: string, packId: string) {
  const response = await fetch(`${API_BASE}/api/admin/keywords/packs/${encodeURIComponent(packId)}`, {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error((payload as {detail?: string}).detail || `API ${response.status}`);
  }
}

export async function getAdminApiPolicy(token: string): Promise<AdminApiPolicyResponse> {
  const response = await fetch(`${API_BASE}/api/admin/api-policy`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminApiPolicyResponse>(response);
}

export async function updateAdminApiPolicy(
  token: string,
  payload: Partial<AdminApiPolicy>
): Promise<{status: string; policy: AdminApiPolicy}> {
  const response = await fetch(`${API_BASE}/api/admin/api-policy`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<{status: string; policy: AdminApiPolicy}>(response);
}

export async function resetAdminApiPolicy(
  token: string
): Promise<{status: string; policy: AdminApiPolicy}> {
  const response = await fetch(`${API_BASE}/api/admin/api-policy/reset`, {
    method: 'POST',
    headers: authHeaders(token)
  });
  return parseJson<{status: string; policy: AdminApiPolicy}>(response);
}

export async function getAdminLLMProviders(token: string): Promise<AdminLLMProviders> {
  const response = await fetch(`${API_BASE}/api/admin/llm-providers`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminLLMProviders>(response);
}

export async function updateAdminLLMProviders(
  token: string,
  payload: Pick<AdminLLMProviders, 'strategy' | 'providers'>
): Promise<AdminLLMProviders> {
  const response = await fetch(`${API_BASE}/api/admin/llm-providers`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminLLMProviders>(response);
}

export async function testAdminLLMProvider(
  token: string,
  payload: {provider_id?: string; provider?: AdminLLMProvider}
): Promise<AdminLLMProviderTestResponse> {
  const response = await fetch(`${API_BASE}/api/admin/llm-providers/test`, {
    method: 'POST',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminLLMProviderTestResponse>(response);
}

export async function getAdminFrontendModules(token: string): Promise<AdminFrontendModules> {
  const response = await fetch(`${API_BASE}/api/admin/frontend-modules`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminFrontendModules>(response);
}

export async function updateAdminFrontendModules(
  token: string,
  payload: Pick<AdminFrontendModules, 'default_module' | 'modules'>
): Promise<AdminFrontendModules> {
  const response = await fetch(`${API_BASE}/api/admin/frontend-modules`, {
    method: 'PUT',
    headers: authHeaders(token, {'Content-Type': 'application/json'}),
    body: JSON.stringify(payload)
  });
  return parseJson<AdminFrontendModules>(response);
}

export async function resetAdminFrontendModules(token: string): Promise<AdminFrontendModules> {
  const response = await fetch(`${API_BASE}/api/admin/frontend-modules/reset`, {
    method: 'POST',
    headers: authHeaders(token)
  });
  return parseJson<AdminFrontendModules>(response);
}

export async function getAdminHomepage(token: string): Promise<AdminHomepageResponse> {
  const response = await fetch(`${API_BASE}/api/admin/homepage`, {
    headers: authHeaders(token),
    cache: 'no-store'
  });
  return parseJson<AdminHomepageResponse>(response);
}

export async function createAdminHomepageRelease(
  token: string,
  payload: {title: string; source_type: 'single_html' | 'zip_package'; html?: string; file?: File | null}
): Promise<AdminHomepageRelease> {
  const formData = new FormData();
  formData.set('title', payload.title);
  formData.set('source_type', payload.source_type);
  if (payload.html) formData.set('html', payload.html);
  if (payload.file) formData.set('file', payload.file);
  const response = await fetch(`${API_BASE}/api/admin/homepage/releases`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData
  });
  return parseJson<AdminHomepageRelease>(response);
}

export async function activateAdminHomepageRelease(token: string, releaseId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/homepage/releases/${encodeURIComponent(releaseId)}/activate`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<{runtime: Record<string, unknown>; release: AdminHomepageRelease}>(response);
}

export async function cloneAdminHomepageRelease(
  token: string,
  releaseId: string
): Promise<AdminHomepageRelease> {
  const response = await fetch(
    `${API_BASE}/api/admin/homepage/releases/${encodeURIComponent(releaseId)}/clone`,
    {
      method: 'POST',
      headers: authHeaders(token)
    }
  );
  return parseJson<AdminHomepageRelease>(response);
}

export async function previewAdminHomepageRelease(token: string, releaseId: string): Promise<Blob> {
  const response = await fetch(
    `${API_BASE}/api/admin/homepage/releases/${encodeURIComponent(releaseId)}/preview`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error((payload as {detail?: string}).detail || `API ${response.status}`);
  }
  return response.blob();
}

export async function getAdminHomepageReleaseSource(
  token: string,
  releaseId: string
): Promise<AdminHomepageSource> {
  const response = await fetch(
    `${API_BASE}/api/admin/homepage/releases/${encodeURIComponent(releaseId)}/source`,
    {
      headers: authHeaders(token),
      cache: 'no-store'
    }
  );
  return parseJson<AdminHomepageSource>(response);
}

export async function updateAdminHomepageReleaseSource(
  token: string,
  releaseId: string,
  html: string,
  expectedSha256: string
): Promise<AdminHomepageUpdateResponse> {
  const response = await fetch(
    `${API_BASE}/api/admin/homepage/releases/${encodeURIComponent(releaseId)}/source`,
    {
      method: 'PUT',
      headers: authHeaders(token, {'Content-Type': 'application/json'}),
      body: JSON.stringify({html, expected_sha256: expectedSha256})
    }
  );
  return parseJson<AdminHomepageUpdateResponse>(response);
}

export async function restoreDefaultAdminHomepage(token: string) {
  const response = await fetch(`${API_BASE}/api/admin/homepage/default`, {
    method: 'POST',
    headers: authHeaders(token)
  });
  return parseJson<{runtime: Record<string, unknown>}>(response);
}

export async function deleteAdminHomepageRelease(token: string, releaseId: string) {
  const response = await fetch(
    `${API_BASE}/api/admin/homepage/releases/${encodeURIComponent(releaseId)}`,
    {
      method: 'DELETE',
      headers: authHeaders(token)
    }
  );
  return parseJson<{status: string}>(response);
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

export async function deleteAdminSetting(token: string, key: string) {
  const response = await fetch(`${API_BASE}/api/admin/settings/${encodeURIComponent(key)}`, {
    method: 'DELETE',
    headers: authHeaders(token)
  });
  return parseJson<{status: string; key: string}>(response);
}

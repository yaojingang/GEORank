import {getByokHeaders} from './byok';
import {ApiRequestError, parseApiResponse} from './api-error';

const API_BASE = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export type SolutionChatRequest = {
  message: string;
  conversation_id?: string;
  diagnostic_report_id?: string;
};

export type SolutionChatResponse = {
  conversation_id: string;
  reply: string;
  recommended_companies: Array<Record<string, unknown>>;
};

export type SolutionConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type SolutionConversationMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  recommended_companies?: Array<Record<string, unknown>>;
  created_at: string;
};

export type SolutionConversationDetail = {
  id: string;
  title: string;
  user_id?: string | null;
  created_at: string;
  updated_at: string;
  messages: SolutionConversationMessage[];
};

export type SolutionStreamEvent =
  | { type: 'text'; content: string }
  | { type: 'companies'; content: Array<Record<string, unknown>> }
  | { type: 'done'; conversation_id: string }
  | { type: 'error'; content: string };

async function parseJson<T>(response: Response): Promise<T> {
  return parseApiResponse<T>(response);
}

export async function listSolutionConversations(
  token: string,
  page = 1,
  size = 20
): Promise<SolutionConversationSummary[]> {
  const search = new URLSearchParams({
    page: String(page),
    size: String(size)
  });
  const response = await fetch(`${API_BASE}/api/solutions/conversations?${search.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: 'no-store'
  });
  return parseJson<SolutionConversationSummary[]>(response);
}

export async function getSolutionConversation(
  token: string,
  conversationId: string
): Promise<SolutionConversationDetail> {
  const response = await fetch(
    `${API_BASE}/api/solutions/conversations/${encodeURIComponent(conversationId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      },
      cache: 'no-store'
    }
  );
  return parseJson<SolutionConversationDetail>(response);
}

export async function streamSolutionChat(
  token: string,
  body: SolutionChatRequest,
  onEvent: (event: SolutionStreamEvent) => void,
  signal?: AbortSignal
) {
  const response = await fetch(`${API_BASE}/api/solutions/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...getByokHeaders()
    },
    body: JSON.stringify(body),
    signal
  });

  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({})) as {
      detail?: string | {code?: string; message?: string; guidance?: Record<string, unknown>; quota?: Record<string, unknown>};
    };
    throw new ApiRequestError(response.status, payload.detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() || '';

    for (const chunk of chunks) {
      const line = chunk
        .split('\n')
        .map((item) => item.trim())
        .find((item) => item.startsWith('data:'));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      onEvent(JSON.parse(payload) as SolutionStreamEvent);
    }
  }
}

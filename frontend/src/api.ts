/**
 * API types and fetch helper.
 *
 * The TypeScript types here mirror the backend's Pydantic schemas
 * (ChatRequest, ChatResponse, ToolTraceEntry). When the backend schemas
 * change, update these in lockstep.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export interface ToolTraceEntry {
  tool: string;
  args: Record<string, unknown>;
  ok: boolean;
  result_summary: string;
  error?: string | null;
  result?: {
    rows?: { dimension: string; value: number }[];
    metric?: string;
    group_by?: string | null;
    aggregation?: string;
  } | null;
}

export interface ChatResponse {
  answer: string;
  trace: ToolTraceEntry[];
  sources: string[];
  conversation_id: string;
}

export interface ConversationSummary {
  conversation_id: string;
  started_at: string;
  last_at: string;
  turn_count: number;
  first_question: string;
}

export interface ConversationTurn {
  created_at: string;
  question: string;
  answer: string;
  trace: ToolTraceEntry[];
  sources: string[];
}

export interface ConversationDetail {
  conversation_id: string;
  turns: ConversationTurn[];
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new ApiError(res.statusText, res.status);
  return res.json();
}

export async function askQuestion(
  question: string,
  conversation_id: string
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id }),
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // body wasn't JSON, keep statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.json();
}

export function listConversations(): Promise<ConversationSummary[]> {
  return getJson<ConversationSummary[]>("/conversations");
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return getJson<ConversationDetail>(`/conversations/${id}`);
}

/** Generate a new conversation ID. Used on app load and "New chat" clicks. */
export function newConversationId(): string {
  return `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}
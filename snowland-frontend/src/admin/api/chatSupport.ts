import adminApi from './axios'

export type ChatSenderType = 'customer' | 'ai' | 'agent' | 'system'
export type HandoffStatus = 'requested' | 'assigned' | 'resolved' | 'cancelled'

export interface ChatSupportMessage {
  id: number
  direction: 'inbound' | 'outbound' | 'system'
  sender_type: ChatSenderType
  content: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface ChatSupportHandoff {
  status: HandoffStatus
  reason: string
  assigned_to: number | null
  assigned_to_name: string | null
  requested_at: string
  updated_at: string
  resolved_at: string | null
}

export interface ChatSupportSession {
  id: string
  channel: 'line'
  external_user_id: string
  contact_name: string
  contact_phone: string
  status: string
  current_step: string
  ai_enabled: boolean
  updated_at: string
  last_message: string
  last_message_at: string | null
  last_sender_type: ChatSenderType | ''
  handoff: ChatSupportHandoff | null
  cart_item_count: number
  reservation_group_ids: number[]
  messages?: ChatSupportMessage[]
}

export type ChatQueue = 'all' | 'waiting' | 'assigned' | 'mine' | 'ai' | 'resolved'

interface ListResponse {
  code: number
  msg: string
  data: {
    list: ChatSupportSession[]
    total: number
    page: number
    page_size: number
  }
}

interface DetailResponse {
  code: number
  msg: string
  data: ChatSupportSession
}

interface ReplyResponse {
  code: number
  msg: string
  data: { message: ChatSupportMessage; replayed: boolean }
}

export async function fetchChatSessions(
  queue: ChatQueue,
  search = '',
): Promise<{ items: ChatSupportSession[]; total: number }> {
  const res = (await adminApi.get('/chat-support/', {
    params: {
      queue,
      search: search || undefined,
      page: 1,
      page_size: 100,
    },
  })) as unknown as ListResponse
  return {
    items: res.data?.list || [],
    total: res.data?.total || 0,
  }
}

export async function fetchChatSession(id: string): Promise<ChatSupportSession> {
  const res = (await adminApi.get(`/chat-support/${id}/`)) as unknown as DetailResponse
  return res.data
}

export async function claimChatSession(id: string): Promise<ChatSupportSession> {
  const res = (await adminApi.post(`/chat-support/${id}/claim/`)) as unknown as DetailResponse
  return res.data
}

export async function replyToChatSession(
  id: string,
  content: string,
  clientMessageId: string,
): Promise<ReplyResponse['data']> {
  const res = (await adminApi.post(`/chat-support/${id}/reply/`, {
    content,
    client_message_id: clientMessageId,
  })) as unknown as ReplyResponse
  return res.data
}

export async function resolveChatSession(
  id: string,
  resumeAi: boolean,
): Promise<ChatSupportSession> {
  const res = (await adminApi.post(`/chat-support/${id}/resolve/`, {
    resume_ai: resumeAi,
  })) as unknown as DetailResponse
  return res.data
}

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Bot,
  CheckCheck,
  CircleUserRound,
  Headphones,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  ShoppingCart,
  Sparkles,
  UserRoundCheck,
} from 'lucide-react'

import {
  claimChatSession,
  fetchChatSession,
  fetchChatSessions,
  replyToChatSession,
  resolveChatSession,
  type ChatQueue,
  type ChatSenderType,
  type ChatSupportMessage,
  type ChatSupportSession,
} from '../api/chatSupport'
import { useNotification } from '../context'

const PRIMARY = '#8b5cf6'

const QUEUES: { value: ChatQueue; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'waiting', label: '待接手' },
  { value: 'mine', label: '我的案件' },
  { value: 'assigned', label: '處理中' },
  { value: 'ai', label: 'AI 處理中' },
  { value: 'resolved', label: '已結案' },
]

const SENDER_LABEL: Record<ChatSenderType, string> = {
  customer: '客人',
  ai: 'AI 客服',
  agent: '真人客服',
  system: '系統',
}

function formatDateTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function displayCustomer(session: ChatSupportSession) {
  if (session.contact_name) return session.contact_name
  if (session.contact_phone) return `電話末碼 ${session.contact_phone.slice(-3)}`
  return `LINE ${session.external_user_id.slice(-8)}`
}

function sessionStatus(session: ChatSupportSession) {
  if (session.handoff?.status === 'requested') {
    return { label: '待真人接手', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' }
  }
  if (session.handoff?.status === 'assigned') {
    return { label: '真人處理中', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' }
  }
  if (session.handoff?.status === 'resolved' && !session.ai_enabled) {
    return { label: '人工模式', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200' }
  }
  if (session.ai_enabled) {
    return { label: 'AI 處理中', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' }
  }
  return { label: 'AI 已暫停', cls: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200' }
}

function getErrorMessage(error: unknown) {
  const err = error as any
  return (
    err?.response?.data?.msg
    || err?.response?.data?.detail
    || err?.message
    || '操作失敗，請稍後再試'
  )
}

function MessageBubble({ message }: { message: ChatSupportMessage }) {
  if (message.sender_type === 'system') {
    return (
      <div className="flex justify-center py-1">
        <div className="max-w-[90%] rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-500 dark:bg-gray-800 dark:text-gray-400">
          {message.content}
        </div>
      </div>
    )
  }

  const fromCustomer = message.sender_type === 'customer'
  const agentName = typeof message.metadata?.sent_by_name === 'string'
    ? message.metadata.sent_by_name
    : ''
  return (
    <div className={`flex ${fromCustomer ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[82%] ${fromCustomer ? '' : 'text-right'}`}>
        <div className={`mb-1 flex items-center gap-1.5 text-[11px] text-gray-400 ${fromCustomer ? '' : 'justify-end'}`}>
          {message.sender_type === 'ai' && <Bot size={12} />}
          {message.sender_type === 'agent' && <Headphones size={12} />}
          <span>
            {message.sender_type === 'agent' && agentName
              ? `${SENDER_LABEL.agent}・${agentName}`
              : SENDER_LABEL[message.sender_type]}
          </span>
          <span>{formatDateTime(message.created_at)}</span>
        </div>
        <div
          className={`whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-left text-sm leading-6 shadow-sm ${
            fromCustomer
              ? 'rounded-tl-md border border-gray-200 bg-white text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100'
              : message.sender_type === 'agent'
                ? 'rounded-tr-md bg-blue-600 text-white'
                : 'rounded-tr-md bg-violet-100 text-violet-950 dark:bg-violet-900/50 dark:text-violet-100'
          }`}
        >
          {message.content}
        </div>
      </div>
    </div>
  )
}

export default function ChatSupportPage() {
  const [queue, setQueue] = useState<ChatQueue>('all')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [replyText, setReplyText] = useState('')
  const messageEndRef = useRef<HTMLDivElement | null>(null)
  const queryClient = useQueryClient()
  const notify = useNotification()

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const sessionsQuery = useQuery({
    queryKey: ['admin', 'chat-support', 'list', queue, search],
    queryFn: () => fetchChatSessions(queue, search),
    refetchInterval: 8000,
  })
  const sessions = sessionsQuery.data?.items || []

  useEffect(() => {
    if (!selectedId && sessions.length) {
      setSelectedId(sessions[0].id)
      return
    }
    if (selectedId && sessions.length && !sessions.some((item) => item.id === selectedId)) {
      setSelectedId(sessions[0].id)
    }
  }, [selectedId, sessions])

  const detailQuery = useQuery({
    queryKey: ['admin', 'chat-support', 'detail', selectedId],
    queryFn: () => fetchChatSession(selectedId as string),
    enabled: Boolean(selectedId),
    refetchInterval: 5000,
  })
  const selected = detailQuery.data
  const messages = useMemo(() => selected?.messages || [], [selected?.messages])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [selectedId, messages.length])

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['admin', 'chat-support', 'list'] }),
      queryClient.invalidateQueries({ queryKey: ['admin', 'chat-support', 'detail', selectedId] }),
    ])
  }

  const claimMutation = useMutation({
    mutationFn: () => claimChatSession(selectedId as string),
    onSuccess: async () => {
      notify.success('已接手對話，AI 已暫停')
      await refresh()
    },
    onError: (error) => notify.error(getErrorMessage(error)),
  })

  const replyMutation = useMutation({
    mutationFn: ({ content, clientMessageId }: { content: string; clientMessageId: string }) =>
      replyToChatSession(selectedId as string, content, clientMessageId),
    onSuccess: async () => {
      setReplyText('')
      notify.success('訊息已傳送到官方 LINE')
      await refresh()
    },
    onError: (error) => notify.error(getErrorMessage(error)),
  })

  const resolveMutation = useMutation({
    mutationFn: (resumeAi: boolean) => resolveChatSession(selectedId as string, resumeAi),
    onSuccess: async (result) => {
      notify.success(result.ai_enabled ? '已結案並恢復 AI' : '已結案並維持人工模式')
      await refresh()
    },
    onError: (error) => notify.error(getErrorMessage(error)),
  })

  const submitReply = (event: FormEvent) => {
    event.preventDefault()
    const content = replyText.trim()
    if (!content || !selectedId || replyMutation.isPending) return
    replyMutation.mutate({
      content,
      clientMessageId: crypto.randomUUID(),
    })
  }

  const requestResolve = (resumeAi: boolean) => {
    const confirmed = window.confirm(
      resumeAi
        ? '確定結束真人處理並恢復 AI 客服嗎？之後客人的新訊息會再次交由 AI 回覆。'
        : '確定將此案件標示為已結案嗎？AI 會繼續保持暫停。',
    )
    if (confirmed) resolveMutation.mutate(resumeAi)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <MessageCircle size={24} style={{ color: PRIMARY }} />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI 客服</h1>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            查看 LINE 對話、接手 AI 案件並直接由官方帳號回覆
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={sessionsQuery.isFetching || detailQuery.isFetching}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          <RefreshCw size={15} className={sessionsQuery.isFetching ? 'animate-spin' : ''} />
          重新整理
        </button>
      </div>

      <div className="grid min-h-[660px] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900 lg:h-[calc(100vh-190px)] lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="flex min-h-[420px] flex-col border-b border-gray-200 dark:border-gray-700 lg:border-b-0 lg:border-r">
          <div className="space-y-3 border-b border-gray-200 p-4 dark:border-gray-700">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="搜尋姓名、電話或對話內容"
                className="w-full rounded-xl border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-violet-200 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
              />
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {QUEUES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setQueue(item.value)}
                  className={`min-w-0 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${
                    queue === item.value
                      ? 'bg-violet-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {sessionsQuery.isLoading ? (
              <div className="flex h-40 items-center justify-center">
                <Loader2 size={28} className="animate-spin text-violet-500" />
              </div>
            ) : sessionsQuery.error ? (
              <div className="p-6 text-center text-sm text-red-600">
                <AlertCircle size={24} className="mx-auto mb-2" />
                {getErrorMessage(sessionsQuery.error)}
              </div>
            ) : sessions.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">
                <MessageCircle size={32} className="mx-auto mb-3 opacity-50" />
                此分類目前沒有對話
              </div>
            ) : (
              sessions.map((session) => {
                const statusInfo = sessionStatus(session)
                const selectedRow = selectedId === session.id
                return (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => setSelectedId(session.id)}
                    className={`w-full border-b border-gray-100 px-4 py-3.5 text-left transition-colors dark:border-gray-800 ${
                      selectedRow
                        ? 'bg-violet-50 dark:bg-violet-950/30'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800/70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                          {displayCustomer(session)}
                        </div>
                        <div className="mt-0.5 truncate text-xs text-gray-400">
                          {formatDateTime(session.last_message_at || session.updated_at)}
                        </div>
                      </div>
                      <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${statusInfo.cls}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-gray-500 dark:text-gray-400">
                      {session.last_message || '尚無訊息'}
                    </p>
                  </button>
                )
              })
            )}
          </div>
        </aside>

        <section className="flex min-h-[620px] min-w-0 flex-col bg-gray-50/70 dark:bg-gray-950/40">
          {!selectedId ? (
            <div className="flex flex-1 flex-col items-center justify-center text-gray-400">
              <MessageCircle size={48} className="mb-3 opacity-40" />
              <p>請選擇一個對話</p>
            </div>
          ) : detailQuery.isLoading || !selected ? (
            <div className="flex flex-1 items-center justify-center">
              <Loader2 size={32} className="animate-spin text-violet-500" />
            </div>
          ) : (
            <>
              <header className="border-b border-gray-200 bg-white px-5 py-4 dark:border-gray-700 dark:bg-gray-900">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
                      <CircleUserRound size={24} />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate font-semibold text-gray-900 dark:text-white">
                          {displayCustomer(selected)}
                        </h2>
                        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${sessionStatus(selected).cls}`}>
                          {sessionStatus(selected).label}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
                        <span>LINE ID：…{selected.external_user_id.slice(-8)}</span>
                        {selected.contact_phone && <span>電話：{selected.contact_phone}</span>}
                        <span className="inline-flex items-center gap-1">
                          <ShoppingCart size={12} /> {selected.cart_item_count} 項
                        </span>
                        {selected.reservation_group_ids.length > 0 && (
                          <span>訂單 #{selected.reservation_group_ids.join('、#')}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {selected.handoff?.assigned_to_name && (
                      <span className="mr-1 text-xs text-gray-500">
                        負責：{selected.handoff.assigned_to_name}
                      </span>
                    )}
                    {selected.ai_enabled
                    || selected.handoff?.status === 'requested'
                    || selected.handoff?.status === 'resolved' ? (
                      <button
                        type="button"
                        onClick={() => claimMutation.mutate()}
                        disabled={claimMutation.isPending}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {claimMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <UserRoundCheck size={14} />}
                        {selected.handoff?.status === 'resolved' && !selected.ai_enabled
                          ? '重新接手'
                          : '接手並暫停 AI'}
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => requestResolve(false)}
                          disabled={resolveMutation.isPending}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
                        >
                          <CheckCheck size={14} />
                          結案・維持人工
                        </button>
                        <button
                          type="button"
                          onClick={() => requestResolve(true)}
                          disabled={resolveMutation.isPending}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-50"
                        >
                          <Sparkles size={14} />
                          結案・恢復 AI
                        </button>
                      </>
                    )}
                  </div>
                </div>
                {selected.handoff?.reason && (
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                    轉接原因：{selected.handoff.reason}
                  </div>
                )}
              </header>

              <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-6">
                {messages.length === 0 ? (
                  <div className="py-16 text-center text-sm text-gray-400">尚無聊天紀錄</div>
                ) : (
                  messages.map((message) => <MessageBubble key={message.id} message={message} />)
                )}
                <div ref={messageEndRef} />
              </div>

              <form onSubmit={submitReply} className="border-t border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
                {selected.ai_enabled && (
                  <div className="mb-2 flex items-center gap-2 text-xs text-amber-600 dark:text-amber-300">
                    <AlertCircle size={13} />
                    傳送人工回覆會自動接手此對話並暫停 AI
                  </div>
                )}
                <div className="flex items-end gap-3">
                  <textarea
                    value={replyText}
                    onChange={(event) => setReplyText(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        event.currentTarget.form?.requestSubmit()
                      }
                    }}
                    rows={2}
                    maxLength={5000}
                    placeholder="輸入真人客服回覆；Enter 傳送，Shift + Enter 換行"
                    className="min-h-[52px] flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm leading-6 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
                  />
                  <button
                    type="submit"
                    disabled={!replyText.trim() || replyMutation.isPending}
                    className="flex h-[52px] items-center justify-center gap-2 rounded-xl bg-violet-600 px-5 text-sm font-semibold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {replyMutation.isPending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                    <span className="hidden sm:inline">傳送</span>
                  </button>
                </div>
                <div className="mt-1.5 text-right text-[10px] text-gray-400">
                  {replyText.length} / 5000
                </div>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

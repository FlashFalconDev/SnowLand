import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Clock, MessageCircle, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useSiteBasePath } from '@/hooks/useSiteBasePath'
import { fetchChatSessions, type ChatQueue } from '../api/chatSupport'

const lineStats = [
  { queue: 'all', label: '總對話數', icon: Users, color: 'bg-blue-500/10 text-blue-500' },
  { queue: 'waiting', label: '待接手', icon: Clock, color: 'bg-amber-500/10 text-amber-500' },
  { queue: 'assigned', label: '真人處理中', icon: MessageCircle, color: 'bg-purple-500/10 text-purple-500' },
  { queue: 'resolved', label: '已結案', icon: CheckCircle2, color: 'bg-green-500/10 text-green-500' },
] satisfies { queue: ChatQueue; label: string; icon: typeof Users; color: string }[]

export default function SocialDashboardPage() {
  const basePath = useSiteBasePath()
  const totals = useQuery({
    queryKey: ['admin', basePath, 'social-dashboard'],
    queryFn: () => Promise.all(lineStats.map(async stat => (await fetchChatSessions(stat.queue, '', 1)).total)),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">數據總覽</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">LINE 對話統計</p>
      </div>
      {totals.isPending && <p role="status">正在載入社群總覽…</p>}
      {totals.isError && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          無法讀取對話統計。<button type="button" className="underline" onClick={() => void totals.refetch()}>重試</button>
        </p>
      )}
      {totals.isSuccess && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {lineStats.map(({ label, icon: Icon, color }, index) => (
            <div key={label} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700/50 dark:bg-gray-800/50">
              <div className="flex flex-wrap items-center gap-3">
                <div className={'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ' + color}>
                  <Icon className="h-5 w-5" aria-hidden />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{totals.data[index]}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <Link to={basePath + '/console/social/inbox'}
        className="block rounded-xl border border-gray-200 bg-white p-5 transition-colors hover:border-purple-500/50 dark:border-gray-700/50 dark:bg-gray-800/50">
        <MessageCircle className="mb-3 h-8 w-8 text-purple-400" aria-hidden />
        <p className="font-medium text-gray-900 dark:text-white">訊息中心</p>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">查看 LINE 對話與客服處理狀態</p>
      </Link>
    </div>
  )
}

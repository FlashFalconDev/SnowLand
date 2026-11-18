// Overview and platform detail layouts from FlashFalcon's social settings.
import {
  ArrowLeft, CheckCircle2, ChevronRight, ExternalLink, Facebook, Instagram,
  MessageSquare, MessagesSquare, Settings, Settings2, Sparkles, type LucideIcon,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'
import { currentClientCode } from '@/utils/tenant'
import { useSiteLink } from '@/hooks/useSiteBasePath'
import { instagramStatusQuery, lineStatusQuery, metaStatusQuery } from '../api/socialChannels'
import InstagramPostSettings from '../components/InstagramPostSettings'
import LineChannelSettings from '../components/LineChannelSettings'
import MetaChannelSettings from '../components/MetaChannelSettings'
import SocialPlatformPageHeader from '../components/SocialPlatformPageHeader'

const CHANNEL_DEFS = [
  {
    type: 'line', label: 'LINE 官方帳號', icon: MessageSquare,
    color: 'bg-green-500/15', iconColor: 'text-green-400', borderColor: 'hover:border-green-500/40',
    description: '使用 Messaging API 串接 LINE 官方帳號，在訊息中心接收與回覆對話。',
    feature: '官方帳號連接', instructions: '設定 Messaging API 的 Channel Token、Channel Secret、Webhook URL。',
    settings: 'line-oa?tab=basic',
  },
  {
    type: 'facebook', label: 'Facebook Messenger', icon: MessagesSquare,
    color: 'bg-blue-500/15', iconColor: 'text-blue-400', borderColor: 'hover:border-blue-500/40',
    description: '透過 Meta 一鍵授權連接粉絲專頁。Messenger 收發待開通。',
    feature: '一鍵授權連接', instructions: '使用 Facebook 帳號授權，再選擇要綁定的粉絲專頁。',
    settings: 'meta?tab=oauth',
  },
  {
    type: 'instagram', label: 'Instagram DM', icon: Instagram,
    color: 'bg-pink-500/15', iconColor: 'text-pink-400', borderColor: 'hover:border-pink-500/40',
    description: '和 Facebook 共用 Meta 授權，連接粉專關聯的 Instagram 帳號。私訊收發待開通。',
    feature: '一鍵授權連接（透過 Meta）', instructions: 'Instagram 與 Facebook 共用授權流程，請在同一頁完成連接。',
    settings: 'meta?tab=oauth',
  },
  {
    type: 'instagram-posts', label: 'Instagram 貼文同步', icon: Instagram,
    color: 'bg-pink-500/15', iconColor: 'text-pink-400', borderColor: 'hover:border-pink-500/40',
    description: '將官方 Instagram 的公開貼文同步到 SnowLand 官網。',
    feature: '同步設定', instructions: '授權官方帳號，並查看最近同步時間。',
    settings: 'channels/instagram-posts/settings',
  },
] as const

type Channel = (typeof CHANNEL_DEFS)[number]
type ChannelState = { label: string; linked?: boolean; name?: string }

function useChannelStates(tenant: string) {
  const line = useQuery(lineStatusQuery(tenant))
  const meta = useQuery(metaStatusQuery(tenant))
  const instagram = useQuery(instagramStatusQuery(tenant))
  const lineData = line.data
  const metaData = meta.data
  const instagramData = instagram.data
  const postsEnabled = instagramData?.connected && instagramData.enabled

  function state(query: { isPending: boolean; isError: boolean }, status: ChannelState): ChannelState {
    if (query.isPending) return { label: '載入中' }
    if (query.isError) return { label: '無法取得狀態' }
    return status
  }

  return {
    line: state(line, {
      label: lineData?.verified ? '已連接' : lineData?.enabled ? '待驗證 Webhook' : lineData?.legacy ? '沿用既有頻道' : lineData?.runtime_ready ? '未連接' : '待平台開通',
      linked: lineData?.verified,
      name: lineData?.display_name,
    }),
    facebook: state(meta, {
      label: metaData?.page_id ? '已綁定帳號' : metaData?.platform_ready ? '未連接' : '待平台開通',
      linked: Boolean(metaData?.page_id),
      name: metaData?.page_name,
    }),
    instagram: state(meta, {
      label: metaData?.instagram_name ? '已綁定帳號' : metaData?.platform_ready ? '未連接' : '待平台開通',
      linked: Boolean(metaData?.instagram_name),
      name: metaData?.instagram_name ? '@' + metaData.instagram_name : undefined,
    }),
    'instagram-posts': state(instagram, {
      label: postsEnabled ? '允許貼文同步' : instagramData?.missing_configuration.length === 0 ? '尚未授權' : '待平台開通',
      linked: postsEnabled,
      name: instagramData?.username ? '@' + instagramData.username : undefined,
    }),
  }
}

function ChannelOverview({ tenant, base }: { tenant: string; base: string }) {
  const states = useChannelStates(tenant)
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700/30 dark:bg-gray-800/30">
        <h1 className="font-semibold text-gray-900 dark:text-white">基礎設定</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          選擇平台管理帳號連接。LINE 驗證後，可在「社群 → 訊息中心」收發對話。
        </p>
      </div>

      <div className="space-y-4">
        {CHANNEL_DEFS.map(def => {
          const status = states[def.type]
          const Icon = def.icon
          return (
            <Link key={def.type} to={base + '/' + def.type} className="block rounded-xl">
              <div className={'cursor-pointer rounded-xl border border-gray-200 bg-white transition-all duration-200 hover:bg-gray-50 dark:border-gray-700/40 dark:bg-gray-800/50 dark:hover:bg-gray-800/80 ' + def.borderColor}>
                <div className="p-5">
                  <div className="flex items-start gap-4">
                    <div className={'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ' + def.color}>
                      <Icon className={'h-6 w-6 ' + def.iconColor} aria-hidden />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <h2 className="font-semibold text-gray-900 dark:text-white">{def.label}</h2>
                        <span className={'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ' + (status.linked
                          ? 'border-green-500/30 bg-green-500/15 text-green-700 dark:text-green-400'
                          : 'border-gray-500/30 bg-gray-500/15 text-gray-500 dark:text-gray-400')}>
                          {status.linked && <CheckCircle2 className="h-3 w-3" aria-hidden />}{status.label}
                        </span>
                      </div>
                      <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">{def.description}</p>
                      <div className="flex flex-wrap gap-2">
                        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-gray-700/50 dark:text-gray-400">{def.feature}</span>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-gray-400" aria-hidden />
                  </div>
                </div>
                {status.linked && status.name && (
                  <div className="flex items-center justify-between gap-3 border-t border-gray-100 px-5 py-2.5 text-xs dark:border-gray-700/30">
                    <span className="break-all text-gray-500 dark:text-gray-400">{status.name}</span>
                    <span className="shrink-0 text-violet-700 dark:text-violet-300">查看設定</span>
                  </div>
                )}
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} aria-label={label} title={label}
      className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-700/50 dark:hover:text-white">
      <ArrowLeft className="h-5 w-5" aria-hidden />
    </Link>
  )
}

function ChannelDetail({ base, channel }: { base: string; channel: Channel }) {
  const Icon = channel.icon
  const settingsPath = useSiteLink('/console/social/' + channel.settings)
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <BackLink to={base} label="返回基礎設定" />
        <div className={'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ' + channel.color}>
          <Icon className={'h-6 w-6 ' + channel.iconColor} aria-hidden />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{channel.label}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">管理此平台的連接與設定</p>
        </div>
      </div>
      <Link to={settingsPath} className="block rounded-xl">
        <div className="cursor-pointer rounded-xl border border-gray-200 bg-white p-5 transition-all duration-200 hover:border-purple-500/40 hover:bg-gray-50 dark:border-gray-700/40 dark:bg-gray-800/50 dark:hover:bg-gray-800/80">
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-700/50">
              <Settings className="h-5 w-5 text-gray-500 dark:text-gray-300" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="mb-0.5 font-medium text-gray-900 dark:text-white">{channel.feature}</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">{channel.instructions}</p>
            </div>
            <ExternalLink className="h-4 w-4 shrink-0 text-gray-400 dark:text-gray-500" aria-hidden />
          </div>
        </div>
      </Link>
    </div>
  )
}

const SETTINGS: Partial<Record<Channel['type'], {
  label: string; tab: string; icon: LucideIcon; tabIcon: LucideIcon;
  form: typeof LineChannelSettings;
}>> = {
  line: { label: 'LINE OA', tab: '基本設定', icon: Settings2, tabIcon: Settings2, form: LineChannelSettings },
  facebook: { label: 'FB / IG', tab: '一鍵授權', icon: Facebook, tabIcon: Sparkles, form: MetaChannelSettings },
  'instagram-posts': { label: 'Instagram 貼文同步', tab: '同步設定', icon: Instagram, tabIcon: Settings2, form: InstagramPostSettings },
}

function ChannelSettings({ tenant, base, channel }: { tenant: string; base: string; channel: Channel }) {
  const status = useChannelStates(tenant)[channel.type]
  const fields = SETTINGS[channel.type]
  if (!fields) return <Navigate to={base + '/' + channel.type} replace />

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <BackLink to={base + '/' + channel.type} label={'返回 ' + channel.label} />
      <SocialPlatformPageHeader
        icon={<fields.icon className="h-6 w-6" aria-hidden />}
        title={fields.label}
        description={channel.description}
        statusLabel={status.label}
        statusTone={status.linked ? 'green' : 'amber'}
      >
        {status.name && <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-200">{status.name}</span>}
      </SocialPlatformPageHeader>
      <div className="overflow-x-auto border-b border-gray-200 dark:border-gray-700">
        <span className="inline-flex items-center gap-2 whitespace-nowrap border-b-2 border-violet-600 px-4 py-3 text-sm font-medium text-violet-700 dark:text-violet-300">
          <fields.tabIcon size={16} aria-hidden />{fields.tab}
        </span>
      </div>
      <fields.form key={tenant} tenantCode={tenant} />
    </div>
  )
}

export default function SocialSyncPage({ settings = false, legacy = false, settingsChannel }: {
  settings?: boolean; legacy?: boolean; settingsChannel?: 'line' | 'facebook'
}) {
  const params = useParams()
  const channel = settingsChannel ?? params.channel
  const { search, hash } = useLocation()
  const tenant = currentClientCode()
  const socialBase = '/' + tenant + '/console/social'
  const base = socialBase + '/channels'
  if (legacy || !channel) {
    const callback = new URLSearchParams(search)
    if (callback.has('meta') || (legacy && channel === 'meta')) {
      if (!callback.has('tab')) callback.set('tab', 'oauth')
      return <Navigate to={socialBase + '/meta?' + callback.toString() + hash} replace />
    }
    if (callback.has('ig') || (legacy && channel === 'instagram')) {
      return <Navigate to={base + '/instagram-posts/settings' + search + hash} replace />
    }
    if (legacy && channel === 'line') {
      return <Navigate to={socialBase + '/line-oa' + (search || '?tab=basic') + hash} replace />
    }
    if (legacy) return <Navigate to={base + search + hash} replace />
    return <ChannelOverview key={tenant} tenant={tenant} base={base} />
  }

  const platform = CHANNEL_DEFS.find(def => def.type === channel)
  if (!platform) return <Navigate to={base} replace />
  if (settings && (channel === 'line' || channel === 'facebook')) {
    const [path, defaultTab] = platform.settings.split('?')
    return <Navigate to={socialBase + '/' + path + (search || '?' + defaultTab) + hash} replace />
  }
  return settings || settingsChannel
    ? <ChannelSettings key={tenant + '/' + channel} tenant={tenant} base={base} channel={platform} />
    : <ChannelDetail base={base} channel={platform} />
}

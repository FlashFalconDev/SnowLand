import type { ReactNode } from 'react'

type Tone = 'green' | 'blue' | 'red' | 'amber' | 'gray'

const toneClasses: Record<Tone, { icon: string; status: string }> = {
  green: {
    icon: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300',
    status: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
  },
  blue: {
    icon: 'bg-blue-500/10 text-blue-600 dark:text-blue-300',
    status: 'bg-blue-500/10 text-blue-700 dark:text-blue-200',
  },
  red: {
    icon: 'bg-red-500/10 text-red-600 dark:text-red-300',
    status: 'bg-red-500/10 text-red-700 dark:text-red-200',
  },
  amber: {
    icon: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
    status: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
  },
  gray: {
    icon: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-200',
    status: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-200',
  },
}

type Props = {
  icon: ReactNode
  title: string
  description: string
  statusLabel: string
  statusTone?: Tone
  children?: ReactNode
  actions?: ReactNode
}

export default function SocialPlatformPageHeader({
  icon,
  title,
  description,
  statusLabel,
  statusTone = 'gray',
  children,
  actions,
}: Props) {
  const tone = toneClasses[statusTone]

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span className={`inline-flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl ${tone.icon}`}>
            {icon}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold text-gray-900 dark:text-white">{title}</h1>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone.status}`}>{statusLabel}</span>
            </div>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-gray-500 dark:text-gray-400">{description}</p>
            {children ? <div className="mt-3 flex flex-wrap gap-2">{children}</div> : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2 lg:justify-end">{actions}</div> : null}
      </div>
    </section>
  )
}

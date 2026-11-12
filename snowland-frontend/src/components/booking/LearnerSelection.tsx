import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import bookingApi from '@/api/axios'
import { useSiteLocale } from '@/contexts/SiteLocale'
import type { CartItem } from '@/types/booking'

type Profile = { id: number; name: string }
export type LearnerChoices = Record<string, Array<number | null>>

export function useLearnerProfiles(client: string, account?: string | number) {
  const queryKey = ['learner-profiles', client, account]
  const query = useQuery({
    queryKey,
    queryFn: async () => (await bookingApi.get('/learner-profiles/') as unknown as { profiles: Profile[] }).profiles,
  })
  return { ...query, queryKey }
}

export function AddLearnerProfile({ queryKey }: { queryKey: unknown[] }) {
  const { t } = useSiteLocale()
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const cache = useQueryClient()
  const create = useMutation({
    mutationFn: async () => await bookingApi.post('/learner-profiles/', { action: 'create', name }) as unknown as Profile,
    onSuccess: profile => {
      cache.setQueryData<Profile[]>(queryKey, previous => [...(previous || []), profile])
      setName('')
      setMessage(t('已新增學員檔案'))
    },
  })
  return <div className="mt-3">
    <div className="flex flex-wrap items-end gap-2">
      <label className="text-sm font-semibold">{t('新學員姓名')}<input maxLength={120} value={name} onChange={event => { setName(event.target.value); setMessage(''); create.reset() }} className="mt-1 block min-h-11 max-w-full rounded border border-slate-300 px-3" /></label>
      <button type="button" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()} className="min-h-11 rounded-full border border-[#2b5f8f] px-4 text-sm font-semibold text-[#2b5f8f] disabled:opacity-50">{t('新增學員檔案')}</button>
    </div>
    {create.isError && <p role="alert" className="mt-2 text-sm text-red-700">{t('無法新增學員，請再試一次')}</p>}
    {message && <p role="status" className="mt-2 text-sm text-green-700">{message}</p>}
  </div>
}

export function CheckoutLearners({ cart, client, account, choices, onChange }: {
  cart: CartItem[]; client: string; account?: string | number; choices: LearnerChoices; onChange: (value: LearnerChoices) => void
}) {
  const { t } = useSiteLocale()
  const query = useLearnerProfiles(client, account)
  const profiles = query.data || []
  return <section className="mb-6 rounded border border-slate-200 bg-white p-4">
    <h3 className="font-semibold">{t('選擇上課學員')}</h3>
    <p className="mt-1 text-sm text-slate-600">{t('為每個名額選擇學員，讓課後評量接續同一人的歷程。尚未確定的名額可以稍後綁定。')}</p>
    {query.isError ? <p role="alert" className="mt-2 text-sm text-red-700">{t('無法載入學員檔案')} <button type="button" onClick={() => void query.refetch()} className="underline">{t('重新載入')}</button></p> :
      query.isPending ? <p role="status" className="mt-2 text-sm">{t('載入學員中…')}</p> : <>
        {cart.map((group, groupIndex) => {
          const selected = choices[group.id]?.length === group.peopleCount ? choices[group.id] : Array<number | null>(group.peopleCount).fill(null)
          return <fieldset key={group.id} className="mt-4 grid gap-2 sm:grid-cols-2">
            <legend className="text-sm font-semibold">{t('第 {number} 組：{name}', { number: groupIndex + 1, name: group.resortName })}</legend>
            {selected.map((value, index) => <label className="text-sm" key={index}>
              {t('學員 {number}', { number: index + 1 })}
              <select value={value ?? ''} onChange={event => {
                const next = [...selected]
                next[index] = event.target.value ? Number(event.target.value) : null
                onChange({ ...choices, [group.id]: next })
              }} className="mt-1 block min-h-11 w-full rounded border border-slate-300 px-2">
                <option value="">{t('稍後綁定')}</option>
                {profiles.map(profile => <option key={profile.id} value={profile.id} disabled={profile.id !== value && selected.includes(profile.id)}>{profile.name}</option>)}
              </select>
            </label>)}
          </fieldset>
        })}
        <AddLearnerProfile queryKey={query.queryKey} />
      </>}
  </section>
}

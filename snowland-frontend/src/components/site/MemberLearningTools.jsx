import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import bookingApi from '@/api/axios';
import { currentClientCode } from '@/utils/tenant';
import { useSiteLocale } from '@/contexts/SiteLocale';
import { AddLearnerProfile, useLearnerProfiles } from '../booking/LearnerSelection';

export function MemberLearnerFilter({ account, value, onChange }) {
  const { t } = useSiteLocale();
  const query = useLearnerProfiles(currentClientCode(), account);
  return <section className="mt-5 rounded border border-slate-200 bg-white p-4">
    <label className="text-sm font-semibold">{t('按學員查看歷程')}
      <select value={value} onChange={event => onChange(event.target.value)} className="mt-1 block min-h-11 w-full max-w-xs rounded border border-slate-300 px-3">
        <option value="">{t('全部學員')}</option>
        {(query.data || []).map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
        <option value="unlinked">{t('尚未連結的舊紀錄')}</option>
      </select>
    </label>
    {query.isError && <p role="alert" className="mt-2 text-sm text-red-700">{t('無法載入學員檔案')} <button type="button" className="underline" onClick={() => void query.refetch()}>{t('重新載入')}</button></p>}
    {query.isSuccess && <AddLearnerProfile queryKey={query.queryKey} />}
  </section>;
}

export function ManageLearnerProfiles({ account }) {
  const { t } = useSiteLocale();
  const query = useLearnerProfiles(currentClientCode(), account);
  return <details className="mt-4 rounded border border-slate-200 bg-white p-3">
    <summary className="cursor-pointer text-sm font-semibold">{t('管理學員檔案')}</summary>
    {query.isSuccess && <AddLearnerProfile queryKey={query.queryKey} />}
    {query.isError && <p role="alert">{t('無法載入學員檔案')} <button type="button" className="underline" onClick={() => void query.refetch()}>{t('重新載入')}</button></p>}
  </details>;
}

export function LinkCourseLearner({ form, account, onSaved }) {
  const { t } = useSiteLocale();
  const query = useLearnerProfiles(currentClientCode(), account);
  const [profile, setProfile] = useState('');
  const link = useMutation({
    mutationFn: () => bookingApi.post('/learner-profiles/', { action: 'bind', member_id: form.id, profile_id: Number(profile) }),
    onSuccess: onSaved,
  });
  if (!form.can_link_learner && !form.learner_id) return null;
  return <div className="mb-2 rounded border border-slate-200 bg-white px-3 py-2 text-sm">
    {form.learner_id ? <p role="status">{t('已連結學員：{name}', { name: query.data?.find(row => row.id === form.learner_id)?.name || form.member_name })}</p> : <>
      <label>{t('學員 {number} 的學習檔案', { number: form.student_number })}
        <select value={profile} onChange={event => { setProfile(event.target.value); link.reset(); }} className="ml-2 min-h-11 rounded border border-slate-300 px-2">
          <option value="">{t('請選擇學員')}</option>
          {(query.data || []).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <button type="button" disabled={!profile || link.isPending} onClick={() => link.mutate()} className="ml-2 min-h-11 font-semibold text-[#2b5f8f] disabled:opacity-50">{t('連結學習檔案')}</button>
      {link.isError && <p role="alert" className="text-red-700">{t(link.error?.response?.data?.error || '連結失敗，請再試一次')}</p>}
    </>}
  </div>;
}

export function MemberCourseAlbums({ account }) {
  const { t } = useSiteLocale();
  const cache = useQueryClient();
  const key = ['course-albums', currentClientCode(), account];
  const [mine, setMine] = useState(false);
  const query = useQuery({ queryKey: key, queryFn: () => bookingApi.get('/course-albums/') });
  const change = useMutation({
    mutationFn: data => bookingApi.patch('/course-albums/', data),
    onSuccess: () => cache.invalidateQueries({ queryKey: key }),
  });
  const albums = (query.data?.albums || []).map(album => ({
    ...album, assets: mine ? album.assets.filter(asset => asset.tagged_member_ids.length) : album.assets,
  })).filter(album => album.assets.length);
  return <section className="mt-7 rounded border border-slate-200 bg-white p-4 sm:p-5">
    <h3 className="text-lg font-semibold">{t('課程相簿')}</h3>
    <p className="mt-1 text-sm text-slate-600">{t('同堂學員可以查看共用照片與影片。認領只會加入個人相簿。')}</p>
    <div className="mt-2 flex flex-wrap gap-2">
      {[[false, '共用相簿'], [true, '我的照片與影片']].map(([value, label]) => <button type="button" key={label} onClick={() => setMine(value)} aria-pressed={mine === value}
        className={`min-h-11 rounded-full border px-4 text-sm font-semibold ${mine === value ? 'border-[#2b5f8f] bg-[#2b5f8f] text-white' : 'border-slate-300 text-[#2b5f8f]'}`}>{t(label)}</button>)}
    </div>
    {query.isPending && <p role="status" className="mt-3 text-sm">{t('載入相簿中…')}</p>}
    {query.isError && <p role="alert" className="mt-3 text-sm text-red-700">{t('無法載入相簿')} <button type="button" className="underline" onClick={() => void query.refetch()}>{t('重新載入')}</button></p>}
    {change.isError && <p role="alert" className="mt-3 text-sm text-red-700">{t('未能儲存認領，請再試一次')}</p>}
    {query.isSuccess && !albums.length && <p className="mt-3 text-sm text-slate-600">{t(mine ? '還沒有認領的照片或影片' : '目前沒有課程照片或影片')}</p>}
    {albums.map(album => <article key={album.id} className="mt-4 rounded border border-slate-200 p-3">
      <h4 className="font-semibold">{album.date} {album.start_time} · {album.course_name}</h4>
      <p className="mt-1 text-xs text-slate-600">{t('訂單')} {album.order_number}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {album.assets.map(asset => <div key={asset.id} className="min-w-0 rounded border border-slate-200 p-2">
          {asset.type === 'video' ? <video src={asset.url} controls preload="metadata" className="aspect-video w-full object-contain" /> :
            <a href={asset.url} target="_blank" rel="noreferrer"><img loading="lazy" src={asset.url} alt={t('課程相簿照片')} className="aspect-video w-full object-contain" /></a>}
          <div className="mt-2 flex flex-wrap gap-2">{album.members.map(member => {
            const tagged = asset.tagged_member_ids.includes(member.id);
            return <button type="button" key={member.id} aria-pressed={tagged} disabled={change.isPending}
              className="min-h-11 rounded-full border border-slate-300 px-3 text-sm font-semibold text-[#2b5f8f] disabled:opacity-50"
              onClick={() => change.mutate({ asset_id: asset.id, member_id: member.id, tagged: !tagged })}>
              {t(tagged ? '取消認領：{name}' : '認領給：{name}', { name: member.name })}
            </button>;
          })}</div>
        </div>)}
      </div>
    </article>)}
  </section>;
}

import React, { useState } from 'react';
import { useSiteLocale } from '../../contexts/SiteLocale';

const regions = ['北海道', '湯澤地區', '白馬地區', '其他日本雪場', '日本以外'];
const disciplines = [['snowboard', '單板 Snowboard'], ['ski', '雙板 Ski']];
const button = 'min-h-11 rounded-lg border border-[#cbd5e1] px-4 text-sm font-semibold disabled:opacity-40';

export default function PreCourseExperience({ assessment, setAssessment, skills, skillOptions, toggleSkill }) {
  const { t } = useSiteLocale();
  const [step, setStep] = useState(0);
  const { kind = '', recent = '', areas = [], boards = [], resort = '', notes = '', finished = false } = assessment;
  const update = patch => setAssessment({ ...assessment, ...patch, finished: false });
  const toggle = (field, selected, choice) => update({
    [field]: selected.includes(choice) ? selected.filter(item => item !== choice) : [...selected, choice],
  });
  const totalSteps = recent === 'yes' ? 4 : 1;
  const reviewComplete = boards.every(board => skills[`${board}_skills`]?.length > 0);
  const ready = kind && (step === 0 ? recent : step === 1 ? areas.length : step === 2 ? boards.length : reviewComplete);
  const complete = () => {
    if (recent === 'no' && kind === 'new') {
      for (const [board] of disciplines) {
        const field = `${board}_skills`;
        if (!skills[field].includes('無經驗')) toggleSkill(field, '無經驗');
      }
    }
    setAssessment({ ...assessment, finished: true });
  };

  return <section className="space-y-4 rounded-sm border border-[#dbe3ec] p-4" aria-label={t('程度自評')}>
    <h6 className="font-semibold">{t('程度自評')}</h6>
    <div className="flex flex-wrap gap-2" aria-label={t('學員類型')}>
      {[['new', '新生'], ['returning', '舊生']].map(([id, label]) => <button key={id} type="button" aria-pressed={kind === id} className={`${button} ${kind === id ? 'bg-[#e8f2fb]' : ''}`} onClick={() => {
        if (kind !== id) { setStep(0); setAssessment({ kind: id }); }
      }}>{t(label)}</button>)}
    </div>
    {kind && (finished ? <div className="flex flex-wrap items-center gap-3">
      <p role="status" className="text-sm text-[#2b5f8f]">{t('程度自評已完成')}</p>
      <button type="button" className={button} onClick={() => { setStep(0); update({}); }}>{t('修改程度自評')}</button>
    </div> : <>
      <p aria-live="polite" className="text-sm text-[#64748b]">{step + 1} / {totalSteps}</p>
      {step === 0 && <fieldset className="space-y-2">
        <legend className="font-semibold">{t(kind === 'returning' ? '前次課程結束後，還有再滑過雪嗎？' : '你有滑雪經驗嗎？')}</legend>
        {[['yes', '有'], ['no', '沒有']].map(([id, label]) => <button key={id} type="button" aria-pressed={recent === id} className={`${button} mr-2 ${recent === id ? 'bg-[#e8f2fb]' : ''}`} onClick={() => update({ recent: id, ...(id === 'no' ? { areas: [], boards: [], resort: '', notes: '' } : {}) })}>{t(label)}</button>)}
      </fieldset>}
      {step === 1 && <fieldset className="space-y-2">
        <legend className="font-semibold">{t('曾經在哪些地區／雪場滑過？')}</legend>
        <div className="flex flex-wrap gap-2">{regions.map(area => <label key={area} className="flex min-h-11 items-center gap-2 rounded border border-[#dbe3ec] px-3 text-sm"><input type="checkbox" checked={areas.includes(area)} onChange={() => toggle('areas', areas, area)} />{t(area)}</label>)}</div>
        <label className="block text-sm">{t('曾滑過的雪場名稱（選填）')}<input maxLength={250} value={resort} onChange={event => update({ resort: event.target.value })} className="mt-1 min-h-11 w-full rounded border border-[#cbd5e1] px-3" /></label>
      </fieldset>}
      {step === 2 && <fieldset className="space-y-2">
        <legend className="font-semibold">{t('你曾有過的滑雪經驗？')}</legend>
        <div className="flex flex-wrap gap-2">{disciplines.map(([id, label]) => <label key={id} className="flex min-h-11 items-center gap-2 rounded border border-[#dbe3ec] px-3 text-sm"><input type="checkbox" checked={boards.includes(id)} onChange={() => toggle('boards', boards, id)} />{t(label)}</label>)}</div>
      </fieldset>}
      {step === 3 && <>
        {disciplines.filter(([id]) => boards.includes(id)).map(([id, label]) => {
          const field = `${id}_skills`;
          return <fieldset key={id} className="max-h-64 overflow-auto rounded border border-[#dbe3ec] px-3">
            <legend className="font-semibold">{t(label)} {t('程度自我評估')}</legend>
            {(skillOptions?.[field] || []).map(([value, text]) => <label key={value} className="flex min-h-11 items-center gap-2 py-2 text-sm"><input type="checkbox" checked={skills[field].includes(value)} onChange={() => toggleSkill(field, value)} />{t(text)}</label>)}
          </fieldset>;
        })}
        <label className="block text-sm">{t('目前滑行遇到的問題')}<textarea rows={3} maxLength={500} value={notes} onChange={event => update({ notes: event.target.value })} className="mt-1 w-full rounded border border-[#cbd5e1] p-2" /></label>
      </>}
      <div className="flex gap-2">
        <button type="button" className={button} disabled={step === 0} onClick={() => setStep(step - 1)}>{t('上一步')}</button>
        <button type="button" className={`${button} bg-[#e8f2fb]`} disabled={!ready} onClick={() => step + 1 === totalSteps ? complete() : setStep(step + 1)}>{t(step + 1 === totalSteps ? '完成程度自我評估' : '下一步')}</button>
      </div>
    </>)}
  </section>;
}

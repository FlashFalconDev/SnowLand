import { useState, type FormEvent } from 'react'
import { DISCIPLINES, RATINGS, saveAssessmentRubric, type Discipline, type DisciplineRubric, type Rating, type RubricConfig, type SkillRule } from '../api/assessment'

const field = 'min-h-11 min-w-0 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900'
const button = 'min-h-11 rounded-md border px-3 text-sm disabled:opacity-40'
const levels = [1, 2, 3, 4, 5, 6]

export default function AssessmentSettings({config, onSaved, reload}:{
  config:RubricConfig; onSaved:(value:RubricConfig)=>void; reload:()=>unknown
}) {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  return <div className="mb-4">
    <button type="button" aria-expanded={open} onClick={()=>setOpen(!open)} className={button}>技術評量設定</button>
    {message && <p role="status" className="mt-2 text-sm text-emerald-700 dark:text-emerald-300">{message}</p>}
    {open && <SettingsEditor key={config.revision} config={config} reload={reload} onSaved={value=>{
      onSaved(value); setOpen(false); setMessage('評量設定已儲存')
    }}/>}
  </div>
}

function SettingsEditor({config, onSaved, reload}:{config:RubricConfig;onSaved:(value:RubricConfig)=>void;reload:()=>unknown}) {
  const [draft, setDraft] = useState(config.rubric)
  const [discipline, setDiscipline] = useState<Discipline>('snowboard')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const current = draft.disciplines[discipline]
  const skills = current.sections.flatMap(section=>section.skills)
  const update = (value:Partial<DisciplineRubric>) => setDraft({...draft,disciplines:{...draft.disciplines,[discipline]:{...current,...value}}})
  const changeRule = (index:number, value:Partial<SkillRule>) => update({
    rules:current.rules.map((rule,i)=>i===index?{...rule,...value}:rule),
  })
  const save = async (event:FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try { onSaved(await saveAssessmentRubric(config.revision,draft)) }
    catch (failure) {
      const data=(failure as {response?:{data?:{rubric?:string[];msg?:string}}}).response?.data
      setError(data?.rubric?.[0] || data?.msg || '設定未儲存，請稍後再試')
    } finally { setBusy(false) }
  }
  return <form onSubmit={save} className="mt-3 space-y-4 rounded-lg border p-3">
    <p className="text-sm">設定只影響本校新評量。已儲存的評量會沿用原版本及評分名稱。</p>
    <fieldset disabled={busy} className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-3">{RATINGS.map(rating=><label key={rating} className="grid text-sm">
        評分 {rating} 名稱<input className={field} maxLength={100} value={draft.ratings[rating]}
          onChange={event=>setDraft({...draft,ratings:{...draft.ratings,[rating]:event.target.value}})}/>
      </label>)}</div>
      <label className="grid max-w-xs text-sm">評量類別<select className={field} value={discipline} onChange={event=>setDiscipline(event.target.value as Discipline)}>
        {Object.entries(DISCIPLINES).map(([key,label])=><option key={key} value={key}>{label}</option>)}
      </select></label>
      <label className="grid max-w-xs text-sm">有評分時的起始等級<select className={field} value={current.entry_level}
        onChange={event=>update({entry_level:Number(event.target.value)})}>
        <option value={0}>未達級</option>{levels.map(level=><option key={level} value={level}>LV{level}</option>)}
      </select></label>
      <details className="rounded-md border px-3">
        <summary className="min-h-11 cursor-pointer py-3 font-semibold">技術項目</summary>
        {current.sections.map(section=><div key={section.id} className="mb-4 space-y-2">
          <label className="grid text-sm">分組名稱<input className={field} maxLength={100} value={section.title}
            onChange={event=>update({sections:current.sections.map(row=>row.id===section.id?{...row,title:event.target.value}:row)})}/></label>
          {section.skills.map((skill,index)=><div key={skill.id} className="flex gap-2">
            <input aria-label={`${section.title} 技術項目 ${index+1}`} className={`${field} flex-1`} maxLength={100} value={skill.title}
              onChange={event=>update({sections:current.sections.map(row=>row.id===section.id?{...row,
                skills:row.skills.map(item=>item.id===skill.id?{...item,title:event.target.value}:item)}:row)})}/>
            <button type="button" className={button} onClick={()=>{
              if(current.rules.some(rule=>rule.criteria.some(criteria=>criteria.skill===skill.id))){
                setError('此項目仍用於升級規則，請先移除對應條件');return
              }
              setError('');update({sections:current.sections.map(row=>row.id===section.id?{...row,skills:row.skills.filter(item=>item.id!==skill.id)}:row)})
            }}>移除</button>
          </div>)}
          <button type="button" className={button} disabled={skills.length>=100 || section.skills.length>=50}
            onClick={()=>update({sections:current.sections.map(row=>row.id===section.id?{...row,
              skills:[...row.skills,{id:crypto.randomUUID(),title:''}]}:row)})}>新增{section.title}項目</button>
        </div>)}
      </details>
      <details className="rounded-md border px-3">
        <summary className="min-h-11 cursor-pointer py-3 font-semibold">升級規則</summary>
        <p className="mb-3 text-xs">同一等級可有多條規則，符合任一條即可達級。每條可要求全部條件或任一條件，評分可高於設定門檻。</p>
        {current.rules.map((rule,index)=>{
          const unused=skills.find(skill=>!rule.criteria.some(criterion=>criterion.skill===skill.id))
          return <fieldset key={index} className="mb-3 space-y-2 rounded-md border p-2">
            <legend className="px-1 text-sm font-semibold">規則 {index+1}</legend>
            <div className="flex flex-wrap gap-2">
              <select aria-label="達成等級" className={field} value={rule.level} onChange={event=>changeRule(index,{level:Number(event.target.value)})}>
                {levels.map(level=><option key={level} value={level}>LV{level}</option>)}
              </select>
              <select aria-label="達成方式" className={field} value={rule.match}
                onChange={event=>changeRule(index,{match:event.target.value as SkillRule['match']})}>
                <option value="all">全部條件達成</option><option value="any">任一條件達成</option>
              </select>
              <button type="button" className={button} onClick={()=>update({rules:current.rules.filter((_,i)=>i!==index)})}>移除規則</button>
            </div>
            {rule.criteria.map((criterion,i)=><div key={i} className="flex flex-wrap gap-2">
              <select aria-label="規則技術項目" className={`${field} max-w-full`} value={criterion.skill}
                onChange={event=>changeRule(index,{criteria:rule.criteria.map((row,j)=>j===i?{...row,skill:event.target.value}:row)})}>
                {skills.map(skill=><option key={skill.id} value={skill.id}
                  disabled={skill.id!==criterion.skill && rule.criteria.some(row=>row.skill===skill.id)}>{skill.title || '未命名項目'}</option>)}
              </select>
              <select aria-label="最低評分" className={field} value={criterion.rating}
                onChange={event=>changeRule(index,{criteria:rule.criteria.map((row,j)=>j===i?{...row,rating:Number(event.target.value) as Rating}:row)})}>
                {RATINGS.map(rating=><option key={rating} value={rating}>{draft.ratings[rating]}</option>)}
              </select>
              <button type="button" className={button} disabled={rule.criteria.length===1}
                onClick={()=>changeRule(index,{criteria:rule.criteria.filter((_,j)=>j!==i)})}>移除條件</button>
            </div>)}
            <button type="button" className={button} disabled={!unused}
              onClick={()=>unused && changeRule(index,{criteria:[...rule.criteria,{skill:unused.id,rating:2}]})}>新增條件</button>
          </fieldset>
        })}
        <button type="button" className={`${button} mb-3`} disabled={!skills.length || current.rules.length>=30}
          onClick={()=>update({rules:[...current.rules,{level:2,match:'all',criteria:[{skill:skills[0].id,rating:2}]}]})}>新增升級規則</button>
      </details>
      <button type="submit" className="min-h-11 rounded-md bg-violet-600 px-4 text-sm font-semibold text-white">
        {busy?'儲存中…':'儲存評量設定'}
      </button>
    </fieldset>
    {error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error} <button type="button" className={button} onClick={()=>void reload()}>重新載入</button></p>}
  </form>
}

import { useState } from 'react'
import { DISCIPLINES, RATINGS, type AssessmentRubric, type Discipline, type Rating, type SkillEntries, type SkillEntry, type SkillSnapshot } from '../api/assessment'

const emptyEntry: SkillEntry = {scores:{},next_steps:[]}

export function SkillReviewFields({rubric, entries, onChange}:{rubric:AssessmentRubric;entries:SkillEntries;onChange:(entries:SkillEntries)=>void}) {
  const [discipline, setDiscipline] = useState<Discipline>(entries.ski && !entries.snowboard ? 'ski' : 'snowboard')
  const entry = entries[discipline] || emptyEntry
  const update = (value:SkillEntry) => onChange({...entries,[discipline]:value})
  const setScore = (id:string, rating?:Rating) => {
    const scores = {...entry.scores}
    if (rating) scores[id] = rating
    else delete scores[id]
    update({...entry,scores})
  }
  return <section aria-label="技術評量" className="space-y-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
    <h3 className="font-semibold">技術評量</h3>
    <p className="text-xs text-gray-500 dark:text-gray-400">勾選本堂有評量的技術再評分。下一步練習可另外勾選。</p>
    <div className="flex flex-wrap gap-2">
      {(Object.entries(DISCIPLINES) as [Discipline,string][]).map(([key,label])=><button key={key} type="button"
        aria-pressed={key===discipline} onClick={()=>setDiscipline(key)}
        className={`min-h-11 rounded-lg border px-4 text-sm ${key===discipline?'border-violet-600 bg-violet-600 text-white':''}`}>{label}</button>)}
    </div>
    {rubric.disciplines[discipline].sections.filter(section=>section.skills.length).map(section=><details key={section.id}
      className="rounded-lg border border-gray-200 px-3 dark:border-gray-700">
      <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">
        {section.title}（{section.skills.filter(skill=>entry.scores[skill.id]).length}／{section.skills.length}）
      </summary>
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {section.skills.map(skill=><div key={skill.id} className="space-y-1 py-2 text-sm">
          <label className="flex min-h-11 items-center gap-2 break-words">
            <input type="checkbox" checked={Boolean(entry.scores[skill.id])} onChange={event=>setScore(skill.id,event.target.checked?1:undefined)}/>{skill.title}
          </label>
          <div className="flex flex-wrap items-center gap-x-4 pl-5">
            {entry.scores[skill.id] && <select aria-label={`${skill.title} 評分`} value={entry.scores[skill.id]}
              onChange={event=>setScore(skill.id,Number(event.target.value) as Rating)}
              className="min-h-11 rounded-lg border bg-white px-2 dark:bg-gray-900">
              {RATINGS.map(rating=><option key={rating} value={rating}>{rubric.ratings[rating]}</option>)}
            </select>}
            <label className="flex min-h-11 items-center gap-2">
              <input type="checkbox" aria-label={`${skill.title} 下一步練習`} checked={entry.next_steps.includes(skill.id)}
                onChange={event=>update({...entry,next_steps:event.target.checked?[...entry.next_steps,skill.id]:entry.next_steps.filter(key=>key!==skill.id)})}/>
              下一步練習
            </label>
          </div>
        </div>)}
      </div>
    </details>)}
  </section>
}

export function SkillSnapshotSummary({snapshot}:{snapshot:SkillSnapshot}) {
  return <div className="mt-3 space-y-2 text-sm">{(Object.entries(snapshot.entries) as [Discipline,SkillEntry][]).map(([key,entry])=>{
    const skills = snapshot.rubric.disciplines[key].sections.flatMap(section=>section.skills)
    return <div key={key}><b>{DISCIPLINES[key]}技術評量</b>
      <ul className="ml-4 list-disc">{skills.filter(skill=>entry.scores[skill.id]).map(skill=><li key={skill.id}>
        {skill.title} · {snapshot.rubric.ratings[entry.scores[skill.id]]}
      </li>)}</ul>
      {entry.next_steps.length>0 && <p>下一步練習：{skills.filter(skill=>entry.next_steps.includes(skill.id)).map(skill=>skill.title).join('、')}</p>}
    </div>
  })}</div>
}

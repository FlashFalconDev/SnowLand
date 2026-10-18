import { useMemo, useState } from 'react'
import type { InsuranceRecord } from '../api/operations'

export function insuranceMonthDays(month: string) {
  const [year, number] = month.split('-').map(Number)
  const first = new Date(year, number - 1, 1)
  return [...Array(first.getDay()).fill(null), ...Array.from({ length:new Date(year,number,0).getDate() },(_,index)=>`${month}-${String(index+1).padStart(2,'0')}`)] as (string|null)[]
}

export function insuranceDayRecords(rows: InsuranceRecord[], date: string) {
  return rows.filter(row => row.course_dates.some(day => day.slice(0,10) === date))
}

export default function InsuranceCalendar({ rows, selectedDate, onSelect }: {
  rows: InsuranceRecord[]; selectedDate: string; onSelect: (date:string)=>void
}) {
  const today = new Date()
  const thisMonth = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`
  const [month,setMonth] = useState(thisMonth)
  const days = useMemo(()=>insuranceMonthDays(month),[month])
  const move = (direction:number) => {
    const [year,number] = month.split('-').map(Number), date = new Date(year,number-1+direction,1)
    setMonth(`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}`)
    onSelect('')
  }
  const button = 'min-h-11 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-100'
  return <section aria-label="保險作業月曆" className="mt-5 rounded-lg border border-gray-200 p-3 dark:border-gray-600">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 aria-live="polite" className="font-semibold text-gray-900 dark:text-white">{month.replace('-',' 年 ')} 月</h3>
      <div className="flex flex-wrap gap-2"><button aria-label="保險月曆上一個月" className={button} onClick={()=>move(-1)}>上月</button><button className={button} onClick={()=>{setMonth(thisMonth);onSelect('')}}>本月</button><button aria-label="保險月曆下一個月" className={button} onClick={()=>move(1)}>下月</button></div>
    </div>
    <p className="my-3 text-xs leading-6 text-gray-600 dark:text-gray-300">依上課日期查看目前篩選的學員；點日期看下方名單。同一學員當日只計一次。資料填齊不代表已投保。</p>
    <div className="mb-3 flex flex-wrap gap-2 text-xs"><span className="rounded bg-amber-100 px-2 py-1 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">資料待補</span><span className="rounded bg-blue-100 px-2 py-1 text-blue-900 dark:bg-blue-900/40 dark:text-blue-200">資料已填</span><span className="rounded bg-violet-100 px-2 py-1 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200">尚未投保／處理中</span><span className="rounded bg-green-100 px-2 py-1 text-green-900 dark:bg-green-900/40 dark:text-green-200">已投保</span></div>
    <div className="grid grid-cols-7 text-center text-xs text-gray-500 dark:text-gray-400">{['日','一','二','三','四','五','六'].map(day=><span className="py-2" key={day}>{day}</span>)}</div>
    <div className="grid grid-cols-7 gap-1">{days.map((day,index)=>{
      if (!day) return <div key={`blank-${index}`} />
      const members=insuranceDayRecords(rows,day), missing=members.filter(row=>!row.insurance_completed_at).length
      const insured=members.filter(row=>row.insurance_processing_status==='insured').length
      return <button key={day} aria-pressed={selectedDate===day} aria-label={`${day}，${members.length} 位學員，資料待補 ${missing} 位，資料已填 ${members.length-missing} 位，尚未投保或處理中 ${members.length-insured} 位，已投保 ${insured} 位`} onClick={()=>onSelect(selectedDate===day?'':day)}
        className={`min-h-[84px] min-w-0 rounded-lg border p-1 text-left text-xs sm:p-2 ${selectedDate===day?'border-violet-500 bg-violet-50 ring-1 ring-violet-500 dark:bg-violet-900/30':'border-gray-200 dark:border-gray-700'} text-gray-800 dark:text-gray-100`}>
        <span className="block font-semibold">{Number(day.slice(-2))}</span>
        {!!members.length && <span className="mt-1 grid grid-cols-2 gap-1" aria-hidden="true"><span className="rounded bg-amber-100 text-center text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">{missing}</span><span className="rounded bg-blue-100 text-center text-blue-900 dark:bg-blue-900/40 dark:text-blue-200">{members.length-missing}</span><span className="rounded bg-violet-100 text-center text-violet-900 dark:bg-violet-900/40 dark:text-violet-200">{members.length-insured}</span><span className="rounded bg-green-100 text-center text-green-900 dark:bg-green-900/40 dark:text-green-200">{insured}</span></span>}
      </button>
    })}</div>
    <div className="mt-3 flex min-h-11 flex-wrap items-center justify-between gap-2 text-sm text-gray-700 dark:text-gray-200"><span role="status">{selectedDate ? `${selectedDate}：${insuranceDayRecords(rows,selectedDate).length} 位學員` : '下方顯示全部日期'}</span>{selectedDate && <button className={button} onClick={()=>onSelect('')}>清除日期篩選</button>}</div>
  </section>
}

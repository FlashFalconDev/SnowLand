import type { ScheduleBooking, ScheduleCalendarData, ScheduleLeave } from '../api/schedule'

export function getCoachScheduleRows(coaches: ScheduleCalendarData['coaches'], bookings: ScheduleBooking[], coachFilter: string) {
  const rows = new Map(coaches.map(coach => [`coach-${coach.id}`, { key: `coach-${coach.id}`, id: coach.id as number | null, name: coach.name || `教練 #${coach.id}` }]))
  for (const booking of bookings) {
    const key = booking.coach_id ? `coach-${booking.coach_id}` : 'unassigned'
    if (!rows.has(key)) rows.set(key, { key, id: booking.coach_id || null, name: booking.coach_name || '尚未指派' })
  }
  return Array.from(rows.values()).filter(row => !coachFilter || row.name === coachFilter)
}

export default function CoachScheduleTable({ coaches, leaves, bookings, days, coachFilter, isOutsideWindow, onOpenOrder, onSelectDate }: {
  coaches: ScheduleCalendarData['coaches']; leaves: ScheduleLeave[]; bookings: ScheduleBooking[]
  days: Array<{ date: Date; dateStr: string }>; coachFilter: string
  isOutsideWindow: (date: string) => boolean; onOpenOrder: (booking: ScheduleBooking) => void; onSelectDate: (date: string) => void
}) {
  const rows = getCoachScheduleRows(coaches, bookings, coachFilter)
  return <>
    <p className="border-b border-gray-200 px-4 py-3 text-xs leading-6 text-gray-600 dark:border-gray-700 dark:text-gray-300">
      固定左欄找教練、上欄找日期，可左右捲動。橘色「指定」與一般課程分色；請假只顯示已核准日期。雪場篩選只篩課程，不隱藏請假；「未排課」不代表可接課。
    </p>
    {rows.length === 0 ? <p className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">目前範圍沒有教練或排課資料。</p> :
      <div role="region" aria-label="教練排班表，可左右捲動" tabIndex={0} className="max-h-[70vh] max-w-full overflow-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-500">
        <table className="w-full border-separate border-spacing-0 text-sm" style={{ minWidth: 128 + days.length * 168 }}>
          <caption className="sr-only">教練與日期排班；空白不代表可接課，點課程查看訂單。</caption>
          <thead className="sticky top-0 z-20">
            <tr><th scope="col" className="sticky left-0 z-30 w-32 min-w-32 border-b border-r border-gray-200 bg-gray-50 p-3 text-left text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white">教練</th>
              {days.map(day => <th scope="col" key={day.dateStr} className="min-w-40 border-b border-r border-gray-200 bg-gray-50 p-1 dark:border-gray-700 dark:bg-gray-900">
                <button type="button" disabled={isOutsideWindow(day.dateStr)} onClick={() => onSelectDate(day.dateStr)} className="min-h-11 w-full rounded-lg px-2 font-medium text-gray-900 hover:bg-violet-50 disabled:text-gray-400 dark:text-white dark:hover:bg-gray-700 dark:disabled:text-gray-500">
                  {day.date.getMonth() + 1}/{day.date.getDate()}（{'日一二三四五六'[day.date.getDay()]}）
                </button>
              </th>)}
            </tr>
          </thead>
          <tbody>{rows.map(row => <tr key={row.key}>
            <th scope="row" className="sticky left-0 z-10 max-w-32 break-words border-b border-r border-gray-200 bg-white p-3 text-left align-top font-semibold text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-white">
              {row.name}{rows.filter(other => other.name === row.name).length > 1 && <span className="block text-xs font-normal text-gray-500 dark:text-gray-400">#{row.id}</span>}
            </th>
            {days.map(day => {
              const outside = isOutsideWindow(day.dateStr)
              const dayBookings = bookings.filter(booking => booking.date === day.dateStr && (row.id ? booking.coach_id === row.id : !booking.coach_id)).sort((a,b) => a.start_time.localeCompare(b.start_time))
              const onLeave = !outside && leaves.some(leave => leave.coach_id === row.id && leave.start_date <= day.dateStr && leave.end_date >= day.dateStr)
              return <td key={day.dateStr} className="border-b border-r border-gray-200 bg-white p-2 align-top dark:border-gray-700 dark:bg-gray-800">
                {outside ? <p className="py-2 text-xs text-gray-400">超出可查看期間</p> : <div className="space-y-2">
                  {onLeave && <p className="rounded-md bg-rose-100 px-2 py-2 text-xs font-semibold text-rose-800 dark:bg-rose-900/40 dark:text-rose-200">休假（已核准）</p>}
                  {dayBookings.map(booking => {
                    const label = booking.event_type === 'equipment_assistance' ? '裝備協助' : booking.event_type === 'photo' ? '攝影' : booking.is_preferred_coach ? '指定' : '一般課程'
                    const level = booking.ability_level === 'no_exp' ? '零經驗' : /^level[1-6]$/.test(booking.ability_level || '') ? `Lv${booking.ability_level!.slice(5)}` : '程度未填'
                    const colors = booking.is_preferred_coach ? 'bg-orange-100 text-orange-900 dark:bg-orange-900/40 dark:text-orange-200' : 'bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200'
                    return <button type="button" key={booking.id} onClick={() => onOpenOrder(booking)} aria-label={`${day.dateStr} ${row.name} ${booking.start_time.slice(0,5)} ${label} 查看訂單`} className={`block min-h-11 w-full break-words rounded-lg p-2 text-left text-xs leading-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-500 ${colors}`}>
                      <span className="block font-semibold">{booking.start_time.slice(0,5)}–{booking.end_time.slice(0,5)} · {label}</span>
                      <span className="block">{booking.course_name} · {level}</span>
                      <span className="block">{booking.resort} · {booking.number_of_people} 人</span>
                    </button>
                  })}
                  {!onLeave && dayBookings.length === 0 && <p className="py-2 text-xs text-gray-400 dark:text-gray-500">— 未排課</p>}
                </div>}
              </td>
            })}
          </tr>)}</tbody>
        </table>
      </div>}
  </>
}

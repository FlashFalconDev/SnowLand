import { useState } from 'react'
import type { OrderReservation } from '../api/orders'

const REASON_LABELS = new Map([
  ['tenant_mismatch', '不屬於此公司'],
  ['campus_mismatch', '未加入此校區'],
  ['missing_resort', '未開放此雪場'],
  ['missing_language', '未開放此語言'],
  ['unavailable_status', '教練目前不接課'],
  ['course_type', '未設定此課程類型的授課資格'],
  ['ability_level', '無法教授此學員程度'],
  ['template_roster', '未列入此課程模板的授課名單'],
  ['min_coach_level', '未達此課程模板要求的教練等級'],
  ['rejected', '曾拒接此組課程'],
  ['on_leave', '上課日期有已核准的請假'],
  ['schedule_conflict', '課程時段重疊'],
  ['missing_bookings', '此組課程沒有上課時段'],
])

export default function OrderCoachAvailability({ reservation }: { reservation: OrderReservation }) {
  const [search, setSearch] = useState('')
  const { candidate_status, available_coaches, unavailable_coaches, preferred_coach_id } = reservation
  if (candidate_status === 'error') {
    return <p role="status" className="text-amber-700 dark:text-amber-300">教練名單載入失敗，請重新開啟訂單再試。</p>
  }

  const unavailable = unavailable_coaches ?? []
  const query = search.trim().toLocaleLowerCase()
  const matching = unavailable.filter((coach) => coach.name.toLocaleLowerCase().includes(query))
  return (
    <>
      {candidate_status === 'ok' && !available_coaches?.length && (
        <p role="status" className="text-gray-600 dark:text-gray-300">目前沒有符合條件的教練。</p>
      )}
      {unavailable.length > 0 && (
        <details className="rounded-md border border-gray-200 dark:border-gray-600">
          <summary className="cursor-pointer rounded-md px-3 py-2.5 text-violet-700 dark:text-violet-300 focus-visible:outline focus-visible:outline-violet-500">
            查看無法選擇的教練及原因（{unavailable.length} 位）
          </summary>
          <div className="space-y-2 px-3 pb-3">
            {unavailable.length > 10 && (
              <input
                type="search"
                aria-label="搜尋無法選擇的教練"
                placeholder="搜尋教練姓名"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="min-h-11 w-full rounded-md border border-gray-200 bg-white px-3 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
              />
            )}
            {matching.length === 0 ? (
              <p className="text-gray-600 dark:text-gray-300">找不到符合搜尋的教練。</p>
            ) : (
              <ul className="max-h-60 divide-y divide-gray-200 overflow-y-auto dark:divide-gray-600">
                {matching.map((coach) => (
                  <li key={coach.id} className="break-words py-2">
                    <p className="font-medium text-gray-900 dark:text-white">
                      {coach.name}{coach.id === preferred_coach_id ? '（目前指派）' : ''}
                    </p>
                    <p className="text-gray-600 dark:text-gray-300">
                      {coach.reason_codes.map((code) => REASON_LABELS.get(code) ?? '不符合條件').join('、')}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </details>
      )}
    </>
  )
}

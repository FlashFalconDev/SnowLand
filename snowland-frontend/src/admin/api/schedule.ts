/**
 * 排課 API
 */
import adminApi from './axios'

export interface ScheduleBooking {
  id: number
  reservation_id?: number
  group_id?: number
  date: string
  start_time: string
  end_time: string
  course_name: string
  coach_name: string
  user_name: string
  resort: string
  number_of_people: number
  is_scheduled: boolean
  status: 'scheduled' | 'pending' | string
  event_type?: 'course' | 'equipment_assistance' | 'photo' | string
  service_type?: 'ski' | 'photo' | string
  equipment_assistance_time_label?: string
  linked_course_date?: string
}

export interface DailyCoachSummary {
  date: string
  total_coaches: number
  booked_coaches: number
  leave_coaches: number
  free_coaches: number
}

export interface ScheduleCalendarData {
  bookings: ScheduleBooking[]
  dailySummary: DailyCoachSummary[]
}

interface ListResp {
  code: number
  msg: string
  data: {
    list: ScheduleBooking[]
    total: number
    daily_summary?: DailyCoachSummary[]
  }
}

export async function fetchScheduleCalendar(params?: { start?: string; end?: string }): Promise<ScheduleCalendarData> {
  const res = (await adminApi.get('/bookings/', { params })) as unknown as ListResp
  return {
    bookings: res.data?.list || [],
    dailySummary: res.data?.daily_summary || [],
  }
}

export async function fetchBookings(params?: { start?: string; end?: string }): Promise<ScheduleBooking[]> {
  const data = await fetchScheduleCalendar(params)
  return data.bookings
}

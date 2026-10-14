/**
 * 排課 API
 */
import adminApi from './axios'

export interface ScheduleBooking {
  id: number
  reservation_id?: number
  group_id?: number
  order_number?: string
  sn?: string
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

export interface GroupCandidate {
  campus_id: number | null
  campus_name: string
  resort_id: number | null
  resort_name: string
  template_id: number
  template_name: string
  date: string
  start_time: string
  end_time: string
  ability_level: string
  registered_students: number
  assigned_students: number
  paid_students?: number
  orders: Array<{ group_id: number; order_number: string; students: number; already_assigned: boolean; payment_status?: string }>
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

export async function fetchGroupCandidates(params: { start: string; end: string }): Promise<GroupCandidate[]> {
  const res = (await adminApi.get('/bookings/group-candidates/', { params })) as unknown as {
    data: { list: GroupCandidate[] }
  }
  return res.data?.list || []
}

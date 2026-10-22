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
  coach_id?: number | null
  ability_level?: string
  is_preferred_coach?: boolean
  user_name: string
  resort: string
  campus_name: string
  campus_is_active: boolean
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
  coaches: Array<{ id: number; name: string }>
  leaves: ScheduleLeave[]
}

export interface ScheduleLeave {
  coach_id: number
  coach_name: string
  start_date: string
  end_date: string
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
  shared_class_id: number | null
  shared_class_status: 'collecting' | 'ready' | 'cancelled' | null
  opening_mode?: 'school' | 'customer' | null
  minimum_students: number | null
  registered_students: number
  assigned_students: number
  paid_students?: number
  orders: Array<{ group_id: number; order_number: string; students: number; already_assigned: boolean; payment_status?: string }>
}

export interface SharedClassCoachOptions {
  shared_class_id: number
  current_coach_id: number | null
  current_coach_name: string | null
  coaches: Array<{ id: number; name: string; availability_status: 'active' | 'passive' }>
}

export interface SharedClassScheduleOptions {
  shared_class_id: number
  date: string
  start_time: string
  end_time: string
  affected_orders: number
  waiver_resign_count: number
  insurance_recheck_count: number
  sessions: Array<{ start_time: string; end_time: string }>
}

export interface SharedClassOpeningOptions {
  enabled: boolean
  campuses: Array<{ id: number; name: string; resorts: Array<{ id: number; name: string }> }>
  templates: Array<{
    id: number; name: string; resort_ids: number[]
    minimum_students: number; max_capacity: number
    sessions: Array<{ id: number; label: string }>
  }>
  levels: Array<[string, string]>
  languages: Array<[string, string]>
}

interface ListResp {
  code: number
  msg: string
  data: {
    list: ScheduleBooking[]
    total: number
    daily_summary?: DailyCoachSummary[]
    coaches?: ScheduleCalendarData['coaches']
    leaves?: ScheduleLeave[]
  }
}

export async function fetchScheduleCalendar(params?: { start?: string; end?: string }): Promise<ScheduleCalendarData> {
  const res = (await adminApi.get('/bookings/', { params })) as unknown as ListResp
  return {
    bookings: res.data?.list || [],
    dailySummary: res.data?.daily_summary || [],
    coaches: res.data?.coaches || [],
    leaves: res.data?.leaves || [],
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

export async function fetchSharedClassOpeningOptions(): Promise<SharedClassOpeningOptions> {
  const res = (await adminApi.get('/bookings/shared-classes/open/')) as unknown as { data: SharedClassOpeningOptions }
  return res.data
}

export async function openSharedClass(input: {
  campus_id: number; resort_id: number; template_id: number; session_id: number
  date: string; ability_level: string; language: string
}): Promise<void> {
  await adminApi.post('/bookings/shared-classes/open/', input)
}

export async function fetchSharedClassCoaches(classId: number): Promise<SharedClassCoachOptions> {
  const res = (await adminApi.get(`/bookings/shared-classes/${classId}/coach/`)) as unknown as {
    data: SharedClassCoachOptions
  }
  return res.data
}

export async function assignSharedClassCoach(classId: number, coachId: number): Promise<void> {
  await adminApi.post(`/bookings/shared-classes/${classId}/coach/`, { coach_id: coachId })
}

export async function fetchSharedClassSchedule(classId: number): Promise<SharedClassScheduleOptions> {
  const res = (await adminApi.get(`/bookings/shared-classes/${classId}/schedule/`)) as unknown as {
    data: SharedClassScheduleOptions
  }
  return res.data
}

export async function rescheduleSharedClass(classId: number, date: string, startTime: string, endTime: string): Promise<string> {
  const res = (await adminApi.post(`/bookings/shared-classes/${classId}/schedule/`, {
    date, start_time: startTime, end_time: endTime,
  })) as unknown as { msg: string }
  return res.msg
}

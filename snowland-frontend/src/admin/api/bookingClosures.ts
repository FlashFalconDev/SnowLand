import adminApi from './axios'

interface ClosureInput {
  resort: number | null
  course_template: number | null
  date_from: string
  date_to: string
  start_time: string | null
  end_time: string | null
  reason: string
}

export interface BookingClosure extends ClosureInput {
  id: number
  resort_name: string | null
  template_name: string | null
}

interface ClosureOptions {
  enabled: boolean
  can_manage_templates: boolean
  resorts: { id: number; name: string }[]
  templates: {
    id: number
    name: string
    can_close_all_resorts: boolean
    resorts: number[]
    sessions: { id: number; start_time: string; end_time: string }[]
  }[]
}

export async function fetchBookingClosures() {
  const result = await adminApi.get('/booking-closures/') as unknown as { data: { list: BookingClosure[] } }
  return result.data.list
}

export async function fetchBookingClosureOptions() {
  const result = await adminApi.get('/booking-closures/options/') as unknown as { data: ClosureOptions }
  return result.data
}

export async function createBookingClosure(input: ClosureInput) {
  return await adminApi.post('/booking-closures/', input) as unknown as { msg: string; warning: string }
}

export async function deleteBookingClosure(id: number) {
  await adminApi.delete(`/booking-closures/${id}/`)
}

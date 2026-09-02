/**
 * 教練請假 API
 */
import adminApi from './axios'

export type LeaveStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'

export interface CoachLeave {
  id: number
  coach: number
  coach_name: string
  coach_img: string
  start_date: string
  end_date: string
  leave_days: number
  reason: string
  status: LeaveStatus
  affected_count: number
  processing_result: string | null
  reviewed_by: number | null
  reviewed_by_name: string | null
  reviewed_at: string | null
  created_at: string
  updated_at: string
}

interface ListResp { code: number; msg: string; data: { list: CoachLeave[]; total: number } }
interface DetailResp { code: number; msg: string; data: CoachLeave }

export async function fetchCoachLeaves(): Promise<CoachLeave[]> {
  const res = (await adminApi.get('/coach-leaves/')) as unknown as ListResp
  return res.data?.list || []
}

export async function reviewLeave(
  id: number,
  status: 'approved' | 'rejected',
  processing_result?: string
): Promise<CoachLeave> {
  const res = (await adminApi.put(`/coach-leaves/${id}/`, {
    status,
    processing_result: processing_result || '',
  })) as unknown as DetailResp
  return res.data
}

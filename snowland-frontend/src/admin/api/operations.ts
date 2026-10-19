import adminApi from './axios'

interface ListResponse<T> { data?: { list?: T[] } }
interface DetailResponse<T> { data: T }

export interface NotificationTemplate {
  id: number; campus: number | null; name: string; event: string; channel: string
  subject: string; body: string; days_before: number; repeat_interval_days: number; course_template_ids: number[]; is_active: boolean; delivery_count: number
}

export interface NotificationDelivery {
  id: number; template_name: string; order_number: string; recipient: string
  channel: string; email_synced: boolean; manual: boolean; local_test: boolean
  scheduled_at: string; sent_at: string | null; status: string; error_message: string
}

export interface PayRule {
  id: number; coach: number; coach_name: string; course_type: number | null; course_type_name?: string; discipline: string; certification_level: string
  hourly_rate: string; specified_fee: number; referral_percent: string
  assistance_hour_factor: string; supervisor_allowance: number; is_active: boolean
}

export interface PayrollCoach {
  id: number; name: string; campus_ids: number[]; can_manage: boolean
}

export interface PayrollStatement {
  id: number; coach: number; coach_name: string; campus: number; campus_name: string
  period_start: string; period_end: string; course_pay: number; specified_fees: number
  referral_commission: number; assistance_pay: number; supervisor_allowance: number
  adjustment: number; total_amount: number; status: string
  published_at: string | null; confirmation_deadline: string | null; review_token: string | null
  confirmed_at: string | null; confirmation_method: string
  confirmation_timezone: string
  document_snapshot: Partial<PayrollDocument>; document_digest: string; signature_file_url: string; signer_name: string; signed_at: string | null
  lines: { id: number; line_type: string; description: string; quantity: string; unit_amount: string; total_amount: number; metadata?: Record<string, unknown> }[]
}

export interface Evaluation {
  can_edit_assessment: boolean
  id: number; member_name: string; coach_name: string; course_date: string
  order_number: string; course_name: string; campus_name: string; resort_name: string
  coach_notes: string; self_assessment: Record<string, unknown>; coach_assessment: Record<string, unknown>
  learning_progress: Record<string, unknown>; trail_names: string[]; available_trails?: string[]; completed_at: string | null
  media: { id: number; media_type: 'photo' | 'video'; url: string; caption: string; is_public: boolean }[]
}

export interface PayrollDocument { title: string; body: string; coach_name: string; campus_name: string; period_start: string; period_end: string; currency: string; total_amount: number; lines: { line_type: string; description: string; quantity: string; unit_amount: string; total_amount: number }[] }
export interface PayrollDocumentSettings { title: string; body: string; is_active: boolean }
export const fetchPayrollDocumentSettings = async (): Promise<PayrollDocumentSettings> => (await adminApi.get('/payroll-statements/document-settings/') as unknown as DetailResponse<PayrollDocumentSettings>).data
export const savePayrollDocumentSettings = async (data: PayrollDocumentSettings): Promise<PayrollDocumentSettings> => (await adminApi.post('/payroll-statements/document-settings/',data) as unknown as DetailResponse<PayrollDocumentSettings>).data
export const generatePayrollDocument = async (id: number): Promise<PayrollStatement> => (await adminApi.post(`/payroll-statements/${id}/document/`) as unknown as DetailResponse<PayrollStatement>).data
export async function uploadPayrollSignature(id: number, file: File, name: string, digest: string, progress: (value:number)=>void): Promise<PayrollStatement> {
  const form = new FormData(); form.append('file',file); form.append('signer_name',name); form.append('document_digest',digest); form.append('accepted','true')
  return (await adminApi.post(`/coach/payroll/${id}/signature/`,form,{headers:{'Content-Type':'multipart/form-data'},onUploadProgress:e=>progress(e.total?Math.min(99,Math.round(e.loaded*100/e.total)):0)}) as unknown as DetailResponse<PayrollStatement>).data
}

export interface StaffBookingLink {
  id: number; campus: number; title: string; url: string; expires_at: string
  is_active: boolean; is_available: boolean; created_by_name: string
}

export interface InsuranceRecord {
  can_remind: boolean
  can_mark_complete: boolean
  can_process_insurance?: boolean
  id: number; member_name: string; order_number: string; sn: string; campus_name: string; age_range: string
  insurance_completed_at: string | null; waiver_completed_at: string | null; waiver_requires_resign: boolean; course_dates: string[]
  insurance_processing_status: 'pending' | 'checking' | 'processing' | 'insured'
  insurance_premium_amount: string | null; insurance_premium_currency: string
  insurance_processing_updated_at: string | null
}

export interface InsuranceRecordDetail extends InsuranceRecord {
  member_email: string
  insurance_data: Record<string, string>
  waiver_signature: string; waiver_document_version: string; waiver_document_snapshot: string
  media_consent: string
}

export interface InsuranceReminderPreview { field:'insurance'|'waiver'; recipient_email:string; subject:string; message:string; action_url:string; local_test:boolean }
export const fetchInsuranceReminder = async(id:number,field:'insurance'|'waiver'):Promise<InsuranceReminderPreview> =>
  (await adminApi.get(`/insurance-records/${id}/reminder/?field=${field}`) as unknown as DetailResponse<InsuranceReminderPreview>).data
export const sendInsuranceReminder = async(id:number,data:{field:'insurance'|'waiver';recipient_email:string;request_key:string}):Promise<{code:number;msg:string}> =>
  await adminApi.post(`/insurance-records/${id}/reminder/`,data) as unknown as {code:number;msg:string}

const list = async <T>(path: string): Promise<T[]> => {
  const response = await adminApi.get(path) as unknown as ListResponse<T>
  return response.data?.list || []
}

export const fetchNotificationTemplates = () => list<NotificationTemplate>('/notification-templates/')
export const fetchNotificationDeliveries = () => list<NotificationDelivery>('/notification-deliveries/')
export interface ManualNotificationDraft {
  kind: 'order' | 'member'; target_id: number; audience: 'owner' | 'participants'; subject: string; body: string
}
export interface ManualNotificationPreview {
  target_label: string; subject: string; body: string; count: number; recipients: { id: number; name: string }[]
}
export const fetchNotificationTargets = (kind: 'order' | 'member', query: string) =>
  list<{ id: number; label: string }>(`/notification-deliveries/targets/?kind=${kind}&q=${encodeURIComponent(query)}`)
export const previewManualNotification = async (data: ManualNotificationDraft): Promise<ManualNotificationPreview> =>
  (await adminApi.post('/notification-deliveries/preview/', data) as unknown as DetailResponse<ManualNotificationPreview>).data
export const sendManualNotification = async (data: ManualNotificationDraft & { request_key: string; expected_recipient_ids: number[] }): Promise<{ count: number; duplicate: boolean }> =>
  (await adminApi.post('/notification-deliveries/send/', data) as unknown as DetailResponse<{ count: number; duplicate: boolean }>).data
export const fetchPayRules = () => list<PayRule>('/coach-pay-rules/')
export interface StaffIncentiveRule {
  id: number; user: number; user_name: string; campus: number; campus_name: string
  completed_order_percent: string; is_active: boolean
}
export interface StaffIncentiveOptions {
  employees: { id: number; name: string; campus_ids: number[] }[]
  campuses: { id: number; name: string }[]
}
export const fetchStaffIncentiveRules = () => list<StaffIncentiveRule>('/staff-incentive-rules/')
export const fetchStaffIncentiveOptions = async (): Promise<StaffIncentiveOptions> =>
  (await adminApi.get('/staff-incentive-rules/employees/') as unknown as DetailResponse<StaffIncentiveOptions>).data
export const saveStaffIncentiveRule = async (data: Partial<StaffIncentiveRule>): Promise<StaffIncentiveRule> =>
  await (data.id ? adminApi.patch(`/staff-incentive-rules/${data.id}/`, data) : adminApi.post('/staff-incentive-rules/', data)) as unknown as StaffIncentiveRule
export const fetchPayrollCoaches = () => list<PayrollCoach>('/coach-pay-rules/coaches/')
export interface StaffIncentiveStatement {
  id: number; user: number; user_name: string; campus: number; campus_name: string; month: string
  percent: string; currency: string; revenue: number; earned_amount: number; refund_deduction: number
  adjustment: number; adjustment_note: string; total_amount: number; status: 'draft' | 'confirmed' | 'paid'
  confirmed_at: string | null; paid_at: string | null; updated_at: string
  lines: { id: number; line_type: 'earning' | 'refund'; order_number: string; event_date: string; base_amount: number; percent: string; amount: number }[]
}
export const fetchStaffIncentiveStatements = () => list<StaffIncentiveStatement>('/staff-incentive-statements/')
export const calculateStaffIncentive = async (data: { user: number; campus: number; month: string }): Promise<StaffIncentiveStatement> =>
  (await adminApi.post('/staff-incentive-statements/calculate/', data) as unknown as DetailResponse<StaffIncentiveStatement>).data
export const updateStaffIncentive = async (id: number, action: 'recalculate' | 'adjust' | 'confirm' | 'record-paid', data: object = {}): Promise<StaffIncentiveStatement> =>
  (await adminApi.post(`/staff-incentive-statements/${id}/${action}/`, data) as unknown as DetailResponse<StaffIncentiveStatement>).data
export const deleteStaffIncentiveDraft = async (id: number): Promise<void> => { await adminApi.delete(`/staff-incentive-statements/${id}/`) }
export const fetchPayrollStatements = () => list<PayrollStatement>('/payroll-statements/')
export const fetchEvaluations = () => list<Evaluation>('/evaluations/')
export const fetchCoachEvaluations = () => list<Evaluation>('/coach/evaluations/')
export const fetchStaffBookingLinks = () => list<StaffBookingLink>('/staff-booking-links/')
export const fetchInsuranceRecords = (status = 'missing') => list<InsuranceRecord>(`/insurance-records/?status=${status}`)

export async function saveInsuranceProcessing(id: number, data: {
  status: InsuranceRecord['insurance_processing_status']; premium_amount: string | null; currency: string
  expected_updated_at: string | null; confirm_insured: boolean
}) {
  await adminApi.post(`/insurance-records/${id}/processing/`, data)
}
export const fetchInsuranceRecord = async (id: number): Promise<InsuranceRecordDetail> =>
  await adminApi.get(`/insurance-records/${id}/`) as unknown as InsuranceRecordDetail

export async function saveNotificationTemplate(data: Partial<NotificationTemplate>) {
  const response = data.id
    ? await adminApi.patch(`/notification-templates/${data.id}/`, data)
    : await adminApi.post('/notification-templates/', data)
  return (response as unknown as DetailResponse<NotificationTemplate>).data
}

export async function savePayRule(data: Partial<PayRule>) {
  const response = data.id
    ? await adminApi.patch(`/coach-pay-rules/${data.id}/`, data)
    : await adminApi.post('/coach-pay-rules/', data)
  return (response as unknown as DetailResponse<PayRule>).data
}

export async function calculatePayroll(data: { coach: number; campus: number; period_start: string; period_end: string }) {
  const response = await adminApi.post('/payroll-statements/calculate/', data)
  return (response as unknown as DetailResponse<PayrollStatement>).data
}

export async function addPayrollAdjustment(id: number, data: { description: string; amount: number }) {
  const response = await adminApi.post(`/payroll-statements/${id}/adjustments/`, data)
  return (response as unknown as DetailResponse<PayrollStatement>).data
}

export async function editPayrollAdjustment(id: number, lineId: number, data: { description: string; amount: number }) {
  const response = await adminApi.post(`/payroll-statements/${id}/adjustments/${lineId}/edit/`, data)
  return (response as unknown as DetailResponse<PayrollStatement>).data
}

export async function removePayrollAdjustment(id: number, lineId: number) {
  await adminApi.post(`/payroll-statements/${id}/adjustments/${lineId}/remove/`)
}

export async function deletePayrollDraft(id: number) {
  await adminApi.delete(`/payroll-statements/${id}/`)
}

export const fetchCoachPayroll = () => list<PayrollStatement>('/coach/payroll/')
export async function payrollReviewAction(id: number, action: 'publish' | 'withdraw' | 'confirm', data: Record<string, unknown> = {}) {
  const path = action === 'confirm' ? 'coach/payroll' : 'payroll-statements'
  const response = await adminApi.post(`/${path}/${id}/${action}/`, data)
  return (response as unknown as DetailResponse<PayrollStatement>).data
}

export async function createStaffBookingLink(data: { campus: number; title: string; expires_at: string; cart_snapshot?: unknown[] }) {
  const response = await adminApi.post('/staff-booking-links/', { ...data, cart_snapshot: data.cart_snapshot || [] })
  return (response as unknown as DetailResponse<StaffBookingLink>).data
}

export async function completeInsuranceRecord(id: number, field: 'insurance' | 'waiver') {
  await adminApi.post(`/insurance-records/${id}/complete/`, { field })
}

export async function updateEvaluation(id: number, data: Partial<Evaluation> & { new_media?: { media_type: 'photo' | 'video'; url: string; is_public: boolean } }, coachView = false) {
  await adminApi.patch(`/${coachView ? 'coach/' : ''}evaluations/${id}/`, data)
}

export async function addEvaluationMedia(id: number, data: { media_type: 'photo' | 'video'; url: string; caption?: string; is_public?: boolean }) {
  await adminApi.post(`/evaluations/${id}/media/`, data)
}

export interface CourseUploadLimits { photo_limit_bytes: number; video_limit_bytes: number; formats: string[] }

export async function fetchCourseUploadLimits(id: number, coachView: boolean) {
  const response = await adminApi.get(`/${coachView ? 'coach/' : ''}evaluations/${id}/upload/`) as unknown as DetailResponse<CourseUploadLimits>
  return response.data
}

export async function uploadCourseFile(id: number, file: File, coachView: boolean, onProgress: (percent: number) => void) {
  const form = new FormData()
  form.append('file', file)
  await adminApi.patch(`/${coachView ? 'coach/' : ''}evaluations/${id}/upload/`, form, {
    headers: { 'Content-Type': undefined }, timeout: 180000,
    onUploadProgress: event => { if (event.total) onProgress(Math.round(event.loaded * 100 / event.total)) },
  })
}

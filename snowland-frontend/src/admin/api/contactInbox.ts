import adminApi from './axios'

export interface ContactMessage {
  id: number; name: string; email: string; phone: string; subject: string; message: string
  status: 'new' | 'processing' | 'resolved'; admin_note: string
  notification_status: 'off' | 'pending' | 'sent' | 'failed'
  updated_by_name: string; created_at: string; updated_at: string
}
export interface ContactSettings { enabled: boolean; notify_enabled: boolean; notify_emails: string[] }
const unwrap = async <T,>(request: Promise<unknown>): Promise<T> => ((await request) as {data: T}).data
export const fetchContactInbox = (page: number, status: string, search: string) => unwrap<{list: ContactMessage[]; total: number; page: number}>(adminApi.get('/contact-inbox/', {params: {page, status, search}}))
export const updateContactMessage = (id: number, data: {status: string; admin_note: string}) => adminApi.patch(`/contact-inbox/${id}/`, data) as unknown as Promise<ContactMessage>
export const retryContactNotification = (id: number) => adminApi.post(`/contact-inbox/${id}/retry-notification/`, {})
export const fetchContactSettings = () => unwrap<ContactSettings>(adminApi.get('/contact-inbox/settings/'))
export const updateContactSettings = (data: ContactSettings) => unwrap<ContactSettings>(adminApi.patch('/contact-inbox/settings/', data))

import { api } from './api'

export type TaskStatus = 'pending' | 'completed'
export type TaskRecord = {
  id: number
  order_no: string
  task_time: string | null
  shop_name: string
  owner_name: string
  principal_amount: number
  order_count: number
  commission_amount: number
  gift_amount: number
  signed_status: TaskStatus
  settlement_status: TaskStatus
  note: string | null
  created_at: string
  updated_at: string
}
export type TaskSummary = {
  total_records: number
  unsettled_principal_total: number
  commission_total: number
  gift_total: number
  principal_total: number
  pending_signed_count: number
  pending_settlement_count: number
  recent_records: TaskRecord[]
}
export type NamedOption = { id: number; name: string; created_at: string }
export const money = (value: number) => `¥ ${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
export const dateTime = (value: string | null) => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '—'
export async function loadTaskData() {
  const [summary, records] = await Promise.all([api<TaskSummary>('/task-bookkeeping/summary'), api<TaskRecord[]>('/task-bookkeeping/records')])
  return { summary, records }
}

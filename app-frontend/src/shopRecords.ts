import { api } from './api'

export type FieldDefinition = {
  id: number
  field_name: string
  label: string
  field_type: 'text' | 'number' | 'date'
  required: boolean
  sort_order: number
  is_visible: boolean
  is_builtin: boolean
}

export type ShopRecord = { id: number; values: Record<string, unknown> }

export async function loadShopData() {
  const [fields, records] = await Promise.all([
    api<FieldDefinition[]>('/custom-fields'),
    api<ShopRecord[]>('/shop-records'),
  ])
  return { fields: fields.filter((field) => field.is_visible).sort((a, b) => a.sort_order - b.sort_order), records }
}

export const displayValue = (value: unknown) => value === null || value === undefined || value === '' ? '—' : String(value)

export function titleFor(record: ShopRecord, fields: FieldDefinition[]) {
  const preferred = ['shop_name', 'store_name', 'name']
  for (const key of preferred) if (record.values[key]) return String(record.values[key])
  const first = fields.find((field) => record.values[field.field_name])
  return first ? String(record.values[first.field_name]) : `店铺记录 #${record.id}`
}

export function searchableText(record: ShopRecord) {
  return Object.values(record.values).map(displayValue).join(' ').toLowerCase()
}

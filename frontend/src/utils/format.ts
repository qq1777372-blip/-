const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/
const NAIVE_DATETIME_RE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/

export function parseApiDateTime(value: string | null | undefined) {
  if (!value) {
    return null
  }

  const normalized = String(value).trim()
  if (!normalized) {
    return null
  }

  if (DATE_ONLY_RE.test(normalized)) {
    const date = new Date(`${normalized}T00:00:00`)
    return Number.isNaN(date.getTime()) ? null : date
  }

  if (NAIVE_DATETIME_RE.test(normalized)) {
    const localDate = new Date(normalized.replace(' ', 'T'))
    return Number.isNaN(localDate.getTime()) ? null : localDate
  }

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function getApiTimestamp(value: string | null | undefined) {
  return parseApiDateTime(value)?.getTime() ?? 0
}

export function formatMoney(value: number | null | undefined) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value ?? 0))
}

export function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const date = parseApiDateTime(value)
  if (!date) {
    return value
  }

  return date.toLocaleDateString('zh-CN')
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const date = parseApiDateTime(value)
  if (!date) {
    return value
  }

  return date.toLocaleString('zh-CN', { hour12: false })
}

export function stringifyRecordValues(values: Record<string, unknown>) {
  return Object.values(values)
    .map((item) => String(item ?? ''))
    .join(' ')
    .toLowerCase()
}

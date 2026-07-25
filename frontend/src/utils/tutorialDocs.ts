import type { SavedLink } from '../types/api'

export const TUTORIAL_DOC_CATEGORY_PREFIX = 'tutorial:'

export function isTutorialDocCategory(category: string | null | undefined) {
  const normalized = String(category ?? '').trim()
  return normalized.startsWith(TUTORIAL_DOC_CATEGORY_PREFIX)
}

export function isTutorialDoc(link: Pick<SavedLink, 'category'>) {
  return isTutorialDocCategory(link.category)
}

export function buildTutorialDocCategory(value: string | null | undefined) {
  const normalized = String(value ?? '').trim()
  return `${TUTORIAL_DOC_CATEGORY_PREFIX}${normalized}`
}

export function stripTutorialDocCategory(value: string | null | undefined) {
  const normalized = String(value ?? '').trim()
  if (!isTutorialDocCategory(normalized)) {
    return normalized
  }

  return normalized.slice(TUTORIAL_DOC_CATEGORY_PREFIX.length).trim()
}

export function getTutorialDocCategoryLabel(value: string | null | undefined) {
  const normalized = stripTutorialDocCategory(value)
  return normalized || '未分类'
}

export function getTutorialDocPlainText(source: string | null | undefined) {
  const normalized = String(source ?? '').trim()
  const strippedHtml = normalized.replace(/<[^>]+>/g, ' ')

  return strippedHtml
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/^\s*[-*+]\s+\[[xX ]\]\s+/gm, '')
    .replace(/\|/g, ' ')
    .replace(/\*\*|__|\*|_/g, '')
    .replace(/~~/g, '')
    .replace(/\r/g, '')
    .replace(/\n{2,}/g, '\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

export function getTutorialDocExcerpt(source: string | null | undefined, maxLength = 140) {
  const normalized = getTutorialDocPlainText(source)
  if (normalized.length <= maxLength) {
    return normalized
  }

  return `${normalized.slice(0, maxLength).trim()}...`
}

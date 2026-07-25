import type { SavedLink } from '../types/api'
import { getApiTimestamp } from './format'
import { isTutorialDoc, stripTutorialDocCategory } from './tutorialDocs'

const URL_PATTERN_SOURCE = 'https?:\\/\\/[^\\s<]+'
const URL_TRAILING_CHARS = '.,!?;:)"\'}]>，。；：！？）》】'

function getTimestamp(value: string | null | undefined) {
  return getApiTimestamp(value)
}

export function isValidHttpUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function stripTrailingUrlPunctuation(value: string) {
  let normalized = value.trim()

  while (normalized && URL_TRAILING_CHARS.includes(normalized[normalized.length - 1] ?? '')) {
    normalized = normalized.slice(0, -1)
  }

  return normalized
}

export function extractUrlsFromText(value: string | null | undefined) {
  if (!value) {
    return []
  }

  const matches = value.match(new RegExp(URL_PATTERN_SOURCE, 'gi')) ?? []
  const urls: string[] = []
  const seen = new Set<string>()

  for (const match of matches) {
    const normalized = stripTrailingUrlPunctuation(match)
    if (!normalized || !isValidHttpUrl(normalized) || seen.has(normalized)) {
      continue
    }

    seen.add(normalized)
    urls.push(normalized)
  }

  return urls
}

export function getPrimaryUrlFromSavedLink(link: Pick<SavedLink, 'url' | 'description'> | null | undefined) {
  if (!link) {
    return null
  }

  const inlineUrls = extractUrlsFromText(link.description)
  if (inlineUrls.length) {
    return inlineUrls[0]
  }

  const normalized = link.url?.trim() ?? ''
  if (normalized && isValidHttpUrl(normalized)) {
    return normalized
  }

  return null
}

export function estimateReadingMinutes(text: string) {
  const normalized = text.replace(/\s+/g, '').trim()
  if (!normalized) {
    return 1
  }

  return Math.max(1, Math.ceil(normalized.length / 320))
}

export function getAuthorInitial(value: string | null | undefined) {
  return (String(value ?? '').trim() || '?').slice(0, 1).toUpperCase()
}

export function getReaderCategoryLabel(value: string | null | undefined) {
  return stripTutorialDocCategory(value) || '未分类'
}

export function getReaderRelatedLinks(current: SavedLink | null | undefined, allLinks: SavedLink[], limit = 5) {
  if (!current) {
    return []
  }

  const currentIsTutorial = isTutorialDoc(current)
  const currentCategory = stripTutorialDocCategory(current.category)
  const sameTypeLinks = allLinks.filter((item) => item.id !== current.id && isTutorialDoc(item) === currentIsTutorial)
  const fallbackLinks = allLinks.filter((item) => item.id !== current.id)

  const prioritizedLinks = [
    ...sameTypeLinks
      .filter((item) => stripTutorialDocCategory(item.category) === currentCategory)
      .sort((left, right) => getTimestamp(right.updated_at) - getTimestamp(left.updated_at)),
    ...sameTypeLinks.sort((left, right) => getTimestamp(right.updated_at) - getTimestamp(left.updated_at)),
    ...fallbackLinks.sort((left, right) => getTimestamp(right.updated_at) - getTimestamp(left.updated_at)),
  ]

  const uniqueLinks: SavedLink[] = []
  const seenIds = new Set<number>()

  for (const item of prioritizedLinks) {
    if (seenIds.has(item.id)) {
      continue
    }

    seenIds.add(item.id)
    uniqueLinks.push(item)

    if (uniqueLinks.length >= limit) {
      break
    }
  }

  return uniqueLinks
}

export function getReaderCategoryStats(
  allLinks: SavedLink[],
  tutorialOnly: boolean | null,
  limit = 6,
) {
  const counts = new Map<string, number>()

  for (const item of allLinks) {
    if (tutorialOnly !== null && isTutorialDoc(item) !== tutorialOnly) {
      continue
    }

    const label = getReaderCategoryLabel(item.category)
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }

  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, 'zh-CN'))
    .slice(0, limit)
}

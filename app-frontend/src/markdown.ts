// Shared between the article editor preview and the reader page so what an
// author previews is exactly what a reader gets.
export type InlineSegment = { type: 'text' | 'link'; value: string; label?: string }
export type ContentBlock = {
  type: 'paragraph' | 'image'
  align: 'left' | 'center' | 'right'
  segments?: InlineSegment[]
  src?: string
  alt?: string
}

const inlinePattern = /\[([^\]]+)]\((https?:\/\/[^)\s]+|\/[^)\s]+)\)|(https?:\/\/[^\s<]+)/g
const imagePattern = /^!\[([^\]]*)]\(([^)]+)\)$/
const trailingUrlPunctuation = new Set('.,!?;:)"\'}]>，。；：！？）】》、'.split(''))

export function inlineSegments(value: string) {
  const segments: InlineSegment[] = []
  let cursor = 0
  for (const match of value.matchAll(inlinePattern)) {
    const start = match.index || 0
    if (start > cursor) segments.push({ type: 'text', value: value.slice(cursor, start) })
    let link = match[2] || match[3] || ''
    let suffix = ''
    while (link && trailingUrlPunctuation.has(link.at(-1) || '')) {
      suffix = (link.at(-1) || '') + suffix
      link = link.slice(0, -1)
    }
    if (link) segments.push({ type: 'link', value: link, label: match[1] || link })
    if (suffix) segments.push({ type: 'text', value: suffix })
    cursor = start + match[0].length
  }
  if (cursor < value.length) segments.push({ type: 'text', value: value.slice(cursor) })
  return segments
}

function cleanMarkdownLine(value: string) {
  return value
    .replace(/^#{1,6}\s+/, '')
    .replace(/^>\s?/, '')
    .replace(/^\s*[-*+]\s+/, '')
    .replace(/\*\*|__|~~|`/g, '')
    .trim()
}

export function parseContent(value?: string, imageAltFallback = '配图') {
  const blocks: ContentBlock[] = []
  let align: ContentBlock['align'] = 'left'
  let lines: string[] = []
  const flush = () => {
    const text = lines.map(cleanMarkdownLine).filter(Boolean).join('\n').trim()
    if (text) blocks.push({ type: 'paragraph', align, segments: inlineSegments(text) })
    lines = []
  }
  for (const rawLine of String(value || '').replace(/\r/g, '').split('\n')) {
    const line = rawLine.trim()
    const alignMatch = line.match(/^:::\s*align-(left|center|right)$/i)
    if (alignMatch) {
      flush()
      align = alignMatch[1].toLowerCase() as ContentBlock['align']
      continue
    }
    if (line === ':::') {
      flush()
      align = 'left'
      continue
    }
    const imageMatch = line.match(imagePattern)
    if (imageMatch) {
      flush()
      blocks.push({ type: 'image', align, alt: imageMatch[1] || imageAltFallback, src: imageMatch[2] })
      continue
    }
    if (!line) {
      flush()
      continue
    }
    lines.push(rawLine)
  }
  flush()
  return blocks
}

export function firstUrl(value: string) {
  return value.match(/https?:\/\/[^\s<]+/i)?.[0] || null
}

export function normalizePath(value?: string) {
  try {
    return new URL(value || '', window.location.origin).pathname
  } catch {
    return value || ''
  }
}

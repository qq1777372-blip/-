import MarkdownIt from 'markdown-it'

const markdownRenderer = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false,
})

const ALIGN_BLOCK_PATTERN = /::: +(align-(left|center|right))\s*\n([\s\S]*?)\n:::/g

type LinkOpenRule = NonNullable<typeof markdownRenderer.renderer.rules.link_open>

const defaultLinkOpen: LinkOpenRule =
  markdownRenderer.renderer.rules.link_open ??
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

markdownRenderer.renderer.rules.link_open = (...args) => {
  const [tokens, idx] = args
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  token.attrJoin('class', 'saved-link-markdown-link')
  return defaultLinkOpen(...args)
}

export function renderSavedLinkMarkdown(source: string | null | undefined) {
  const normalized = String(source ?? '').trim()
  if (!normalized) {
    return ''
  }

  let lastIndex = 0
  let rendered = ''

  for (const match of normalized.matchAll(ALIGN_BLOCK_PATTERN)) {
    const matchIndex = match.index ?? 0
    const fullMatch = match[0] ?? ''
    const alignKey = match[1] ?? 'align-left'
    const blockContent = String(match[3] ?? '').trim()

    if (matchIndex > lastIndex) {
      rendered += markdownRenderer.render(normalized.slice(lastIndex, matchIndex))
    }

    rendered += `<div class="saved-link-${alignKey}">\n${markdownRenderer.render(blockContent)}\n</div>\n`
    lastIndex = matchIndex + fullMatch.length
  }

  if (lastIndex < normalized.length) {
    rendered += markdownRenderer.render(normalized.slice(lastIndex))
  }

  return rendered || markdownRenderer.render(normalized)
}

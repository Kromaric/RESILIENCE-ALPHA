// Documentation du dépôt (dossier docs/), embarquée au build par Vite : c'est le même corpus
// que celui de l'assistant (assistant-rag indexe tous les .md de docs/ sauf api/).
// Modifier docs/ demande donc de rebuilder le dashboard, comme de redémarrer l'assistant.
const markdown = import.meta.glob(['../../../docs/**/*.md', '!../../../docs/api/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
})
const images = import.meta.glob('../../../docs/**/*.{svg,png,jpg}', {
  query: '?url',
  import: 'default',
  eager: true,
})

const ROOT = '../../../docs/'

// Dossier → libellé de la navigation, dans l'ordre d'affichage
const SECTIONS = [
  ['', 'Général'],
  ['runbooks', 'Runbooks'],
  ['alertes', 'Alertes'],
  ['services', 'Services'],
  ['gouvernance', 'Gouvernance'],
]

// Identifiant d'ancre d'un titre (« SC-01 — description » → « sc-01-description »)
export function slugify(text) {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

// Recherche insensible à la casse et aux accents
export const normalize = (text) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

// Titre Markdown sans mise en forme (`code`, **gras**, liens)
const plain = (text) => text.replace(/`/g, '').replace(/\*/g, '').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').trim()

function parse(path, content) {
  const lines = content.split('\n')
  const h1 = lines.find((l) => l.startsWith('# '))
  const name = path.split('/').pop().replace(/\.md$/, '')
  return {
    path,
    folder: path.includes('/') ? path.split('/')[0] : '',
    title: h1 ? plain(h1.slice(2)) : name,
    content,
    toc: lines
      .filter((l) => l.startsWith('## '))
      .map((l) => {
        const title = plain(l.slice(3))
        return { title, id: slugify(title) }
      }),
  }
}

export const pages = Object.entries(markdown)
  .map(([key, content]) => parse(key.slice(ROOT.length), content))
  .sort((a, b) => {
    if (a.path === 'README.md') return -1
    if (b.path === 'README.md') return 1
    return a.title.localeCompare(b.title, 'fr')
  })

export const sections = SECTIONS.map(([folder, title]) => ({
  title,
  pages: pages.filter((p) => p.folder === folder),
})).filter((s) => s.pages.length > 0)

export const defaultPage = pages[0]

export const findPage = (path) => pages.find((p) => p.path === path)

// Résout un lien relatif d'une page (« ../runbooks/x.md#ancre », « services/ ») vers une page
// du dashboard ; null si la cible n'est pas dans docs/ (CADRAGE.md, code source…)
export function resolveLink(fromPath, href) {
  if (!href || /^[a-z]+:/i.test(href) || href.startsWith('#')) return null
  const [target, hash] = href.split('#')
  const resolved = decodeURIComponent(new URL(target, `http://docs/${fromPath}`).pathname.slice(1))
  const page = resolved.endsWith('/')
    ? pages.find((p) => p.path.startsWith(resolved))
    : findPage(resolved)
  return page ? `/docs/${page.path}${hash ? `#${hash}` : ''}` : null
}

export function resolveImage(fromPath, src) {
  if (!src || /^[a-z]+:/i.test(src)) return src
  const resolved = new URL(src, `http://docs/${fromPath}`).pathname.slice(1)
  return images[ROOT + resolved] ?? null
}

// Pages de docs/ citées par une page (pour « Pages liées »)
export function linkedPages(page) {
  const found = new Map()
  for (const [, href] of page.content.matchAll(/\]\(([^)\s]+)\)/g)) {
    const link = resolveLink(page.path, href)
    if (!link) continue
    const target = findPage(link.slice('/docs/'.length).split('#')[0])
    if (target && target.path !== page.path) found.set(target.path, target)
  }
  return [...found.values()]
}

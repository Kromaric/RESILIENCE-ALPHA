import { Children, isValidElement } from 'react'
import { Link } from 'react-router-dom'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Info } from 'lucide-react'
import CodeBlock from './CodeBlock'
import { slugify, resolveLink, resolveImage } from '../../data/docs'

// Texte brut d'un nœud React (pour les ancres des titres)
function textOf(node) {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement(node)) return textOf(node.props.children)
  return ''
}

function Heading({ level, children }) {
  const id = slugify(textOf(children))
  const styles = {
    1: 'text-2xl font-semibold text-gray-100',
    2: 'mt-8 mb-3 text-lg font-semibold text-gray-100',
    3: 'mt-6 mb-2 text-base font-semibold text-gray-100',
    4: 'mt-4 mb-2 text-sm font-semibold text-gray-200',
  }
  const Tag = `h${level}`
  return (
    <Tag id={id} className={`scroll-mt-6 ${styles[level]}`}>
      {children}
    </Tag>
  )
}

export default function MarkdownPage({ page }) {
  const components = {
    h1: ({ children }) => <Heading level={1}>{children}</Heading>,
    h2: ({ children }) => <Heading level={2}>{children}</Heading>,
    h3: ({ children }) => <Heading level={3}>{children}</Heading>,
    h4: ({ children }) => <Heading level={4}>{children}</Heading>,
    p: ({ children }) => <p className="my-3">{children}</p>,
    ul: ({ children }) => <ul className="my-3 list-disc space-y-1.5 pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="my-3 list-decimal space-y-1.5 pl-5">{children}</ol>,
    strong: ({ children }) => <strong className="font-semibold text-gray-100">{children}</strong>,
    hr: () => <hr className="my-6 border-line" />,
    blockquote: ({ children }) => (
      <div className="my-4 flex gap-3 rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-1 text-gray-200">
        <Info size={16} className="mt-3.5 shrink-0 text-blue-300" />
        <div>{children}</div>
      </div>
    ),
    a: ({ href, children }) => {
      if (href?.startsWith('#')) {
        return <a href={href} className="text-accent underline underline-offset-2">{children}</a>
      }
      if (/^https?:/.test(href ?? '')) {
        return (
          <a href={href} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">
            {children}
          </a>
        )
      }
      const to = resolveLink(page.path, href)
      // Cible hors de docs/ (CADRAGE.md, code source) : pas de page à ouvrir dans le dashboard
      if (!to) return <span className="text-gray-200" title={href}>{children}</span>
      return <Link to={to} className="text-accent underline underline-offset-2">{children}</Link>
    },
    img: ({ src, alt }) => {
      const url = resolveImage(page.path, src)
      return url ? <img src={url} alt={alt} className="my-4 max-w-full rounded-md bg-white p-2" /> : null
    },
    table: ({ children }) => (
      <div className="my-4 overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-left text-xs">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-bg text-muted">{children}</thead>,
    tr: ({ children }) => <tr className="border-t border-line first:border-t-0">{children}</tr>,
    th: ({ children }) => <th className="px-3 py-2 font-medium">{children}</th>,
    td: ({ children }) => <td className="px-3 py-2.5 align-top">{children}</td>,
    // Bloc de code : remplacé entièrement par CodeBlock (bouton Copier)
    pre: ({ children }) => {
      const code = Children.only(children)
      const lang = /language-(\w+)/.exec(code.props.className ?? '')?.[1]
      return (
        <div className="my-4">
          <CodeBlock filename={lang ?? 'code'} code={textOf(code.props.children).replace(/\n$/, '')} />
        </div>
      )
    },
    // Code en ligne (les blocs passent par `pre` ci-dessus)
    code: ({ children }) => (
      <code className="rounded bg-bg px-1 font-mono text-xs text-accent">{children}</code>
    ),
  }

  return (
    <article className="text-sm leading-relaxed text-gray-300">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {page.content}
      </Markdown>
    </article>
  )
}

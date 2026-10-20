import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

export default function CodeBlock({ filename, code }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-bg">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="font-mono text-[11px] text-muted">{filename}</span>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-[11px] text-gray-300 hover:text-white"
        >
          {copied ? <Check size={12} className="text-ok" /> : <Copy size={12} />}
          {copied ? 'Copié' : 'Copier'}
        </button>
      </div>
      <pre className="max-h-64 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-gray-300">
        <code>{code}</code>
      </pre>
    </div>
  )
}
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ThumbsUp, ThumbsDown } from 'lucide-react'
import { findPage } from '../../data/docs'

export default function ChatMessage({ message }) {
  const [feedback, setFeedback] = useState(null)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-xl rounded-lg bg-accent/15 px-4 py-3">
          <p className="text-[11px] text-muted">Vous · {message.time}</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-gray-100">{message.text}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-accent text-xs font-semibold text-bg">
        o
      </span>
      <div className="max-w-2xl">
        <p className="text-[11px] text-muted">Assistant · {message.time}</p>

        {message.error ? (
          <p className="mt-1 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-gray-200">
            {message.error}
          </p>
        ) : (
          <>
            <div className="mt-1 space-y-2 text-sm leading-relaxed text-gray-200">
              {message.text.split(/\n{2,}/).map((p, i) => (
                <p key={i} className="whitespace-pre-wrap">{p}</p>
              ))}
            </div>

            {message.sources.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {message.sources.map((s, i) => {
                  const page = findPage(s.doc)
                  const label = (
                    <>
                      <span className="font-mono text-accent">[{i + 1}]</span> {page?.title ?? s.doc}
                    </>
                  )
                  const chip = 'rounded-md border border-line px-2 py-1 text-[11px] text-gray-300'
                  return page ? (
                    <Link key={i} to={`/docs/${page.path}`} title={`docs/${page.path}`} className={`${chip} hover:border-accent hover:text-white`}>
                      {label}
                    </Link>
                  ) : (
                    <span key={i} className={chip}>{label}</span>
                  )
                })}
              </div>
            )}

            <div className="mt-3 flex items-center gap-2 text-[11px] text-muted">
              <span className="font-mono">{message.meta}</span>
              {[['up', ThumbsUp], ['down', ThumbsDown]].map(([key, Icon]) => (
                <button
                  key={key}
                  onClick={() => setFeedback(key)}
                  className={`rounded border border-line p-1 hover:text-white ${feedback === key ? 'text-accent' : ''}`}
                >
                  <Icon size={12} />
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

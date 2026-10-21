import { useEffect, useRef } from 'react'
import Card from '../Card'

const levelColor = {
  INFO: 'text-muted',
  WARN: 'text-warn',
  ERROR: 'text-danger',
  ALERT: 'text-danger',
  ACTION: 'text-accent',
}

export default function LogViewer({ logs }) {
  const boxRef = useRef(null)

  // Défile en bas à chaque nouveau lot de journaux
  useEffect(() => {
    boxRef.current.scrollTop = boxRef.current.scrollHeight
  }, [logs])

  return (
    <Card>
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-gray-100">Journaux et alertes</h3>
        <p className="font-mono text-[11px] text-muted">Loki · SIEM · WAF</p>
      </div>
      <div ref={boxRef} className="max-h-60 overflow-auto rounded-md border border-line bg-bg p-3 font-mono text-[11px]">
        <div className="min-w-[520px] space-y-1.5">
          {logs.map((log) => (
            <div key={log.time} className="grid grid-cols-[95px_55px_90px_1fr] gap-2">
              <span className="text-muted">{log.time}</span>
              <span className={levelColor[log.level]}>{log.level}</span>
              <span className="text-gray-400">{log.source}</span>
              <span className="text-gray-200">{log.msg}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
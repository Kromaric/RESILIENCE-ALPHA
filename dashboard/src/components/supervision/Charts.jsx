import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceArea, ReferenceLine,
} from 'recharts'
import { colors } from '../../theme'

const ticks = (points) => points.filter((_, i) => i % 10 === 0).map((p) => p.time)
const axis = { axisLine: false, tickLine: false, tick: { fill: colors.muted, fontSize: 11 } }
const tooltipStyle = {
  contentStyle: { background: colors.surface, border: `1px solid ${colors.line}`, fontSize: 12 },
  labelStyle: { color: colors.muted },
}

function IncidentArea({ incident }) {
  if (!incident) return null
  return (
    <ReferenceArea
      x1={incident.x1}
      x2={incident.x2}
      fill={colors.danger}
      fillOpacity={0.15}
      label={{ value: 'incident', position: 'insideTop', fill: colors.danger, fontSize: 10 }}
    />
  )
}

export function LatencyChart({ points, incident }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={points} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid stroke={colors.line} vertical={false} />
        <XAxis dataKey="time" ticks={ticks(points)} {...axis} />
        <YAxis {...axis} tickFormatter={(v) => (v >= 1000 ? `${v / 1000} s` : `${v}`)} />
        <Tooltip {...tooltipStyle} formatter={(v) => [`${v} ms`, 'Latence p95']} />
        {IncidentArea({ incident })}
        <Line type="monotone" dataKey="latency" stroke={colors.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function AnomalyChart({ points, incident }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={points} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid stroke={colors.line} vertical={false} />
        <XAxis dataKey="time" ticks={ticks(points)} {...axis} />
        <YAxis domain={[0, 1]} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v) => [v, 'Score']} />
        {IncidentArea({ incident })}
        <ReferenceLine
          y={0.8}
          stroke={colors.warn}
          strokeDasharray="4 4"
          label={{ value: 'seuil 0,80', position: 'insideTopRight', fill: colors.warn, fontSize: 10 }}
        />
        <Line type="monotone" dataKey="anomaly" stroke={colors.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function TransactionsChart({ points, incident }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={points} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid stroke={colors.line} vertical={false} />
        <XAxis dataKey="time" ticks={ticks(points)} {...axis} />
        <YAxis {...axis} />
        <Tooltip {...tooltipStyle} cursor={{ fill: colors.line }} formatter={(v) => [v, 'Transactions / min']} />
        {IncidentArea({ incident })}
        <Bar dataKey="tx" isAnimationActive={false}>
          {points.map((p) => (
            <Cell key={p.time} fill={p.incident ? colors.danger : colors.accent} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

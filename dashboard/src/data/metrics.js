const POINTS = 31 // 30 minutes de fenêtre (une mesure par minute)
const SPIKE_INDEX = 20 // index correspondant à l'instant de l'incident (ex: T - 10 min)

const noise = (i, amp) => Math.sin(i * 1.7) * amp + Math.cos(i * 0.9) * (amp / 2)

export function getSeries(phase, incidentDateStr = null) {
  const incDate = incidentDateStr ? new Date(incidentDateStr) : new Date()
  // Démarre la fenêtre 20 minutes avant l'incident pour que le pic soit à l'index 20
  const startTime = new Date(incDate.getTime() - SPIKE_INDEX * 60 * 1000)

  const labelAt = (index) => {
    const d = new Date(startTime.getTime() + index * 60 * 1000)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  const spikes = {
    latency: { [SPIKE_INDEX]: 1420, [SPIKE_INDEX + 1]: 2180, [SPIKE_INDEX + 2]: 460 },
    anomaly: { [SPIKE_INDEX]: 0.94, [SPIKE_INDEX + 1]: 0.98, [SPIKE_INDEX + 2]: 0.28 },
    tx: { [SPIKE_INDEX]: 38, [SPIKE_INDEX + 1]: 14, [SPIKE_INDEX + 2]: 65 },
  }

  const points = Array.from({ length: POINTS }, (_, i) => {
    const time = labelAt(i)
    if (phase === 'pendant' && i > SPIKE_INDEX + 1) return { time }
    const isIncident = phase !== 'avant' && (i === SPIKE_INDEX || i === SPIKE_INDEX + 1)

    return {
      time,
      incident: isIncident,
      latency: isIncident
        ? spikes.latency[i]
        : Math.max(10, Math.round(15 + noise(i, 4))),
      anomaly: isIncident
        ? spikes.anomaly[i]
        : Math.max(0.01, +(0.04 + noise(i, 0.015)).toFixed(2)),
      tx: isIncident
        ? spikes.tx[i]
        : Math.max(80, Math.round(120 + noise(i, 6))),
    }
  })

  const incident =
    phase === 'avant'
      ? null
      : {
          x1: labelAt(SPIKE_INDEX),
          x2: labelAt(phase === 'pendant' ? SPIKE_INDEX + 1 : SPIKE_INDEX + 2),
        }

  return { points, incident }
}

export function getDynamicResources(phase) {
  if (phase === 'avant') {
    return [
      { label: 'CPU', value: '24 %', percent: 24 },
      { label: 'Mémoire', value: '4,1 / 16 Go', percent: 26 },
      { label: 'Disque SSD', value: '28 / 100 Go', percent: 28 },
      { label: 'Réseau entrant', value: '1,4 Mo/s', percent: 7 },
    ]
  }
  if (phase === 'pendant') {
    return [
      { label: 'CPU', value: '84 %', percent: 84 },
      { label: 'Mémoire', value: '7,9 / 16 Go', percent: 49 },
      { label: 'Disque SSD', value: '28 / 100 Go', percent: 28 },
      { label: 'Réseau entrant', value: '17,8 Mo/s', percent: 89 },
    ]
  }
  // apres ou live nominal
  return [
    { label: 'CPU', value: '26 %', percent: 26 },
    { label: 'Mémoire', value: '4,3 / 16 Go', percent: 27 },
    { label: 'Disque SSD', value: '28 / 100 Go', percent: 28 },
    { label: 'Réseau entrant', value: '1,6 Mo/s', percent: 8 },
  ]
}

export const resources = {
  avant: getDynamicResources('avant'),
  pendant: getDynamicResources('pendant'),
  apres: getDynamicResources('apres'),
}

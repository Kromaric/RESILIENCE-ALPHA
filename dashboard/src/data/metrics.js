const POINTS = 31 // une mesure par minute, 10:20 → 10:50
const SPIKE_START = 21 // 10:41
const PENDANT_END = 23 // 10:43, l'incident est encore en cours

const label = (i) => `10:${String(20 + i).padStart(2, '0')}`
const noise = (i, amp) => Math.sin(i * 1.7) * amp + Math.cos(i * 0.9) * (amp / 2)

// Valeurs pendant l'incident, par index de minute
const spikes = {
  latency: { 21: 900, 22: 2300, 23: 1800, 24: 420 },
  anomaly: { 21: 0.62, 22: 0.94, 23: 0.86, 24: 0.3 },
  tx: { 21: 70, 22: 25, 23: 15, 24: 32 },
}

export function getSeries(phase) {
  const points = Array.from({ length: POINTS }, (_, i) => {
    const time = label(i)
    if (phase === 'pendant' && i > PENDANT_END) return { time } // pas encore de données
    const incident = phase !== 'avant' && i in spikes.latency
    return {
      time,
      incident,
      latency: incident ? spikes.latency[i] : Math.round(190 + noise(i, 12)),
      anomaly: incident ? spikes.anomaly[i] : +(0.1 + noise(i, 0.02)).toFixed(2),
      tx: incident ? spikes.tx[i] : Math.round(120 + noise(i, 6)),
    }
  })

  const incident =
    phase === 'avant'
      ? null
      : { x1: label(SPIKE_START), x2: label(phase === 'pendant' ? PENDANT_END : 24) }

  return { points, incident }
}

export const resources = {
  avant: [
    { label: 'CPU', value: '31 %', percent: 31 },
    { label: 'Mémoire', value: '9,8 / 16 Go', percent: 61 },
    { label: 'Disque SSD', value: '31 / 100 Go', percent: 31 },
    { label: 'Réseau entrant', value: '2,1 Mo/s', percent: 10 },
  ],
  pendant: [
    { label: 'CPU', value: '87 %', percent: 87 },
    { label: 'Mémoire', value: '13,1 / 16 Go', percent: 82 },
    { label: 'Disque SSD', value: '31 / 100 Go', percent: 31 },
    { label: 'Réseau entrant', value: '18,6 Mo/s', percent: 93 },
  ],
  apres: [
    { label: 'CPU', value: '38 %', percent: 38 },
    { label: 'Mémoire', value: '10,2 / 16 Go', percent: 64 },
    { label: 'Disque SSD', value: '31 / 100 Go', percent: 31 },
    { label: 'Réseau entrant', value: '2,4 Mo/s', percent: 12 },
  ],
}
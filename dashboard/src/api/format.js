// Formats d'affichage des données de bo-api (dates en UTC, montants en centimes)
const integer = new Intl.NumberFormat('fr-FR')
const percent = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 1 })

export const formatInt = (n) => integer.format(n)
export const formatPercent = (ratio) => percent.format(ratio)
export const formatHour = (iso) =>
  new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

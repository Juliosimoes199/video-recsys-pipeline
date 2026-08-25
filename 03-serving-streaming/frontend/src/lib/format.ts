export function formatViews(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)} mi`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)} mil`
  return `${count}`
}

export function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const diffSec = Math.max(0, Math.floor(diffMs / 1000))

  const units: [number, string][] = [
    [60, 'segundo'],
    [60, 'minuto'],
    [24, 'hora'],
    [30, 'dia'],
    [12, 'mês'],
    [Number.POSITIVE_INFINITY, 'ano'],
  ]

  let value = diffSec
  let unitName = 'segundo'
  for (const [amount, name] of units) {
    if (value < amount) {
      unitName = name
      break
    }
    value = Math.floor(value / amount)
    unitName = name
  }

  const plural = value === 1 ? '' : unitName === 'mês' ? 'es' : 's'
  return `há ${value} ${unitName}${plural}`
}

export function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = Math.floor(totalSeconds % 60)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`
}

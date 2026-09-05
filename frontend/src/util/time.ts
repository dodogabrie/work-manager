/* Minuti -> resa leggibile. Gli effort restano minuti ovunque tranne qui. */

export function hm(minutes: number): string {
  const m = Math.max(0, Math.round(minutes))
  const h = Math.floor(m / 60)
  const rest = m % 60
  if (!h) return `${rest}m`
  return rest ? `${h}h ${rest}m` : `${h}h`
}

const DAYS = ['dom', 'lun', 'mar', 'mer', 'gio', 'ven', 'sab']
const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']

/** Una data ISO come giorno locale, senza fusi: 'YYYY-MM-DD' è già un giorno. */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function iso(date: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`
}

export function addDays(date: Date, days: number): Date {
  const out = new Date(date)
  out.setDate(out.getDate() + days)
  return out
}

/** Lunedì della settimana che contiene `date`. */
export function weekStart(date: Date): Date {
  return addDays(date, -((date.getDay() + 6) % 7))
}

export function dayLabel(isoDay: string): string {
  const d = parseDay(isoDay)
  return `${DAYS[d.getDay()]} ${d.getDate()}`
}

export function longDay(isoDay: string): string {
  const d = parseDay(isoDay)
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`
}

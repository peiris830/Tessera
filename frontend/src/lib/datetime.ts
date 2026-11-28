/**
 * Event times are stored in UTC and shown in the viewer's local time with the zone offset,
 * e.g. "12 Jul 2027, 19:30 GMT+5:30", so nobody has to guess which zone a time is in.
 * (Venue time zones may be added to the event model later; see docs/design/ui-style.md.)
 */
export function formatEventDateTime(
  iso: string,
  options: { timeZone?: string; locale?: string } = {},
): string {
  const parts = new Intl.DateTimeFormat(options.locale ?? 'en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZoneName: 'shortOffset',
    timeZone: options.timeZone,
  }).formatToParts(new Date(iso))

  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? ''
  const zone = part('timeZoneName').replace(/^GMT\+0$/, 'GMT') // some runtimes write UTC as GMT+0
  return `${part('day')} ${part('month')} ${part('year')}, ${part('hour')}:${part('minute')} ${zone}`
}

/** Short form for dense lists: "12 Jul, 19:30". */
export function formatEventDateShort(iso: string, options: { timeZone?: string } = {}): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: options.timeZone,
  }).format(new Date(iso))
}

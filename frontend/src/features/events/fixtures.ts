/**
 * SAMPLE DATA for the layout preview (step 5a). Synthetic only. Replaced by live Catalogue
 * API data in steps 5c (browse) and 5d (organiser console); delete this file then.
 */
import type { Event } from '../../api/catalogue'

const inDays = (days: number, hour: number, minute = 0) => {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + days)
  d.setUTCHours(hour, minute, 0, 0)
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

export const SAMPLE_EVENTS: Event[] = [
  {
    eventId: 'sample-1',
    title: 'Summer Jazz Night',
    description:
      'An evening of acoustic quintet jazz in the main auditorium. Doors open 45 minutes before the performance, with unreserved seating across the stalls and balcony.\n\nTwo 50-minute sets with a 20-minute interval. Step-free seating on the ground level.',
    venue: { name: 'Test Hall', city: 'Testville' },
    startsAt: inDays(3, 14),
    capacity: 500,
    status: 'PUBLISHED',
  },
  {
    eventId: 'sample-2',
    title: 'String Quartet in the Courtyard',
    description: 'Haydn and Shostakovich under the arches. Bring a cushion; seating is on stone steps.',
    venue: { name: 'Atrium Stage', city: 'Old Quarter' },
    startsAt: inDays(6, 14, 30),
    capacity: 180,
    status: 'PUBLISHED',
  },
  {
    eventId: 'sample-3',
    title: 'Civic Design & Architecture Forum',
    description: 'Talks and a panel on public spaces, followed by a networking reception.',
    venue: { name: 'Forum Auditorium', city: 'Riverport' },
    startsAt: inDays(18, 13),
    capacity: 850,
    status: 'PUBLISHED',
  },
  {
    eventId: 'sample-4',
    title: 'Late Night Electronic Showcase',
    description: 'Four local producers, one long night.',
    venue: { name: 'Foundry Annex', city: 'Milltown' },
    startsAt: inDays(40, 15, 30),
    capacity: 420,
    status: 'PUBLISHED',
  },
  {
    eventId: 'sample-5',
    title: 'Autumn Chamber Recital',
    description: 'Draft: programme still being finalised.',
    venue: { name: 'Civic Conservatory', city: 'Northbridge' },
    startsAt: inDays(75, 14, 30),
    capacity: 320,
    status: 'DRAFT',
  },
  {
    eventId: 'sample-6',
    title: 'Winter Choral Gala',
    description: '',
    venue: { name: 'St. Jude Hall', city: 'Riverport' },
    startsAt: inDays(120, 13, 30),
    capacity: 640,
    status: 'DRAFT',
  },
  {
    eventId: 'sample-7',
    title: 'Spring Brass Matinee',
    description: 'Cancelled due to venue works.',
    venue: { name: 'Bandstand Pavilion', city: 'Milltown' },
    startsAt: inDays(30, 9),
    capacity: 220,
    status: 'CANCELLED',
  },
]

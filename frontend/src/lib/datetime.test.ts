import { formatEventDateShort, formatEventDateTime } from './datetime'

test('shows local time with the zone offset', () => {
  // 14:00 UTC in July is 15:00 in London (BST, GMT+1) and 19:30 in India (GMT+5:30).
  expect(formatEventDateTime('2027-07-12T14:00:00Z', { timeZone: 'Europe/London' })).toBe(
    '12 Jul 2027, 15:00 GMT+1',
  )
  expect(formatEventDateTime('2027-07-12T14:00:00Z', { timeZone: 'Asia/Kolkata' })).toBe(
    '12 Jul 2027, 19:30 GMT+5:30',
  )
})

test('UTC is shown as GMT', () => {
  expect(formatEventDateTime('2027-01-05T09:05:00Z', { timeZone: 'UTC' })).toBe(
    '05 Jan 2027, 09:05 GMT',
  )
})

test('short form for lists', () => {
  expect(formatEventDateShort('2027-07-12T14:00:00Z', { timeZone: 'UTC' })).toBe('12 Jul, 14:00')
})

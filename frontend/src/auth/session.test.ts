import { rolesFromGroups, safeReturnPath } from './session'

test('roles come from the cognito:groups claim, ignoring unknown groups', () => {
  expect(rolesFromGroups(['organiser', 'attendee', 'admin'])).toEqual(['attendee', 'organiser'])
  expect(rolesFromGroups(undefined)).toEqual([])
  expect(rolesFromGroups('organiser')).toEqual([]) // not the array shape ID tokens use
})

test.each([
  ['/organiser/events/abc?x=1', '/organiser/events/abc?x=1'],
  ['/events', '/events'],
])('same-site path %s is kept', (input, expected) => {
  expect(safeReturnPath(input)).toBe(expected)
})

test.each([
  'https://evil.example/',
  '//evil.example',
  '/\\evil.example',
  'javascript:alert(1)',
  '/auth/callback?code=x',
  undefined,
  42,
])('unsafe return address %s falls back to /events', (input) => {
  expect(safeReturnPath(input)).toBe('/events')
})

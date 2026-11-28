import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { AppProviders } from '../app/AppProviders'
import { type Role, type Session, SessionContext } from '../auth/session'

/** A session for tests: signed out unless `as` gives roles. Callbacks are spies. */
export function fakeSession(as?: { email?: string; roles: Role[] }, status?: Session['status']): Session {
  return {
    status: status ?? (as ? 'signedIn' : 'signedOut'),
    user: as ? { email: as.email ?? 'user@example.com', roles: as.roles } : undefined,
    signIn: vi.fn(),
    signOut: vi.fn(),
    getAccessToken: vi.fn(async () => (as ? 'test-access-token' : undefined)),
  }
}

export const organiser = () => fakeSession({ email: 'organiser1@example.com', roles: ['organiser'] })
export const attendee = () => fakeSession({ email: 'attendee1@example.com', roles: ['attendee'] })

/** Render with the real providers, a session and an in-memory router starting at `route`. */
export function renderAt(ui: ReactElement, route = '/', session: Session = fakeSession()) {
  const result = render(
    <MemoryRouter initialEntries={[route]}>
      <AppProviders env="test">
        <SessionContext.Provider value={session}>{ui}</SessionContext.Provider>
      </AppProviders>
    </MemoryRouter>,
  )
  return { ...result, session }
}

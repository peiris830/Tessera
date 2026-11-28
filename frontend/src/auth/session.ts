/**
 * The app's view of "who is signed in". Components use `useSession()` and never the OIDC
 * library directly, so tests can supply a fake session (src/test/render.tsx) and the library
 * stays contained in OidcSessionProvider.tsx.
 *
 * Roles here only decide what the UI shows. Every rule is enforced again by the APIs, which
 * verify the token themselves.
 */
import { createContext, useContext } from 'react'

export const ROLES = ['attendee', 'organiser', 'venue_staff'] as const
export type Role = (typeof ROLES)[number]

export interface SignedInUser {
  email: string
  roles: Role[]
}

export interface Session {
  status: 'loading' | 'signedOut' | 'signedIn'
  user?: SignedInUser
  /** Go to the Cognito login page; come back to `returnTo` (default: the current page). */
  signIn: (returnTo?: string) => void
  /** Revoke the refresh token, forget the tokens and end Cognito's login session. */
  signOut: () => void
  /** Current access token for API calls, or undefined when signed out. */
  getAccessToken: () => Promise<string | undefined>
}

export const SessionContext = createContext<Session | null>(null)

export function useSession(): Session {
  const session = useContext(SessionContext)
  if (session === null) throw new Error('useSession() needs a session provider above it')
  return session
}

export function hasRole(session: Session, role: Role): boolean {
  return session.user?.roles.includes(role) ?? false
}

/** Keep only known roles from the token's `cognito:groups` claim (anything else is ignored). */
export function rolesFromGroups(groups: unknown): Role[] {
  if (!Array.isArray(groups)) return []
  return ROLES.filter((role) => groups.includes(role))
}

/**
 * Only same-site paths may be used as a return address after sign-in, so a crafted link
 * can't send someone to another site (an "open redirect").
 */
export function safeReturnPath(path: unknown): string {
  // "//evil.example" and "/\evil.example" are both treated as another host by browsers.
  if (typeof path !== 'string' || !/^\/(?![/\\])/.test(path)) return '/events'
  if (path.startsWith('/auth/')) return '/events'
  return path
}

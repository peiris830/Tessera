/**
 * Sign-in with Cognito's hosted login page: OAuth 2.0 authorization code flow + PKCE, via
 * oidc-client-ts (protocol) and react-oidc-context (React bindings).
 *
 *  1. signIn() sends the browser to Cognito with a random PKCE challenge and our `state`.
 *  2. Cognito sends it back to /auth/callback?code=...; AuthProvider exchanges the code plus
 *     the PKCE verifier for tokens, and AuthCallbackPage returns the user to their page.
 *  3. Tokens live in sessionStorage (this tab only). Before the access token expires (60 min)
 *     the refresh token gets a new one silently; if that fails, the user is told and signed out.
 */
import { notifications } from '@mantine/notifications'
import type { UserManager } from 'oidc-client-ts'
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AuthProvider, useAuth } from 'react-oidc-context'
import type { AppConfig } from '../config'
import { CALLBACK_PATH, cognitoLogoutUrl, createUserManager } from './oidc'
import { type Session, SessionContext, rolesFromGroups, safeReturnPath } from './session'

function notifyExpired() {
  notifications.show({
    color: 'yellow',
    title: 'Session expired',
    message: 'You have been signed out. Sign in again to continue.',
  })
}

function SessionBridge({
  config,
  userManager,
  children,
}: {
  config: AppConfig
  userManager: UserManager
  children: ReactNode
}) {
  const auth = useAuth()
  const renewStarted = useRef(false)

  const { events, removeUser, signinSilent, user, isLoading } = auth

  const expire = useCallback(() => {
    void removeUser()
    notifyExpired()
  }, [removeUser])

  // Automatic renewal failed (e.g. refresh token revoked or older than 7 days).
  useEffect(() => events.addSilentRenewError(expire), [events, expire])

  // A tab reopened after the access token expired: try the refresh token once.
  const expired = Boolean(user?.expired)
  useEffect(() => {
    if (!expired || isLoading || renewStarted.current) return
    renewStarted.current = true // StrictMode runs effects twice in dev; refresh only once
    signinSilent()
      .catch(expire)
      .finally(() => {
        renewStarted.current = false
      })
  }, [expired, isLoading, signinSilent, expire])

  const session = useMemo<Session>(() => {
    const signedIn = auth.isAuthenticated && auth.user
    return {
      status:
        isLoading || expired ? 'loading' : signedIn ? 'signedIn' : 'signedOut',
      user: signedIn
        ? {
            email: String(auth.user?.profile.email ?? ''),
            roles: rolesFromGroups(auth.user?.profile['cognito:groups']),
          }
        : undefined,
      signIn: (returnTo) => {
        const path = returnTo ?? window.location.pathname + window.location.search
        void auth.signinRedirect({ state: { returnTo: safeReturnPath(path) } })
      },
      signOut: () => {
        void (async () => {
          try {
            await auth.revokeTokens() // the refresh token can no longer mint access tokens
          } catch {
            // Already invalid or offline: signing out locally still matters most.
          }
          await auth.removeUser()
          window.location.assign(cognitoLogoutUrl(config)) // ends Cognito's own login cookie
        })()
      },
      getAccessToken: async () => {
        const current = await userManager.getUser()
        return current && !current.expired ? current.access_token : undefined
      },
    }
  }, [auth, isLoading, expired, config, userManager])

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}

export function OidcSessionProvider({ config, children }: { config: AppConfig; children: ReactNode }) {
  const [userManager] = useState(() => createUserManager(config))
  return (
    <AuthProvider
      userManager={userManager}
      // Only the callback page carries ?code=&state= for us; elsewhere leave the URL alone.
      skipSigninCallback={window.location.pathname !== CALLBACK_PATH}
    >
      <SessionBridge config={config} userManager={userManager}>
        {children}
      </SessionBridge>
    </AuthProvider>
  )
}

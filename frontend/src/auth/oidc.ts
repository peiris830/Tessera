/** OIDC client settings for Cognito (see OidcSessionProvider.tsx for the flow). */
import { UserManager, WebStorageStateStore } from 'oidc-client-ts'
import type { AppConfig } from '../config'

export const CALLBACK_PATH = '/auth/callback'

export function createUserManager(config: AppConfig, origin = window.location.origin) {
  return new UserManager({
    authority: config.cognitoAuthority, // discovery: <issuer>/.well-known/openid-configuration
    client_id: config.cognitoClientId,
    redirect_uri: `${origin}${CALLBACK_PATH}`, // must match the app client's CallbackURLs
    response_type: 'code',
    scope: 'openid email',
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: true, // uses the refresh token shortly before the access token expires
    revokeTokenTypes: ['refresh_token'],
    // Cognito's discovery document doesn't list these; they live on the hosted UI domain.
    metadataSeed: {
      revocation_endpoint: `${config.cognitoHostedUiUrl}/oauth2/revoke`,
      end_session_endpoint: `${config.cognitoHostedUiUrl}/logout`,
    },
  })
}

/** Cognito's sign-out endpoint takes its own parameters (client_id + logout_uri). */
export function cognitoLogoutUrl(config: AppConfig, origin = window.location.origin) {
  const params = new URLSearchParams({ client_id: config.cognitoClientId, logout_uri: `${origin}/` })
  return `${config.cognitoHostedUiUrl}/logout?${params}`
}

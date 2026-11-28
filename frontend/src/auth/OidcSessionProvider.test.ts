import type { AppConfig } from '../config'
import { cognitoLogoutUrl, createUserManager } from './oidc'

const config: AppConfig = {
  catalogueApiUrl: 'https://api.example.test',
  cognitoAuthority: 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example',
  cognitoClientId: 'exampleclientid',
  cognitoHostedUiUrl: 'https://tessera-dev-0123abcd.auth.us-east-1.amazoncognito.com',
}

test('the OIDC client matches the Cognito app client settings', () => {
  const { settings } = createUserManager(config, 'http://localhost:5173')

  expect(settings.authority).toBe(config.cognitoAuthority)
  expect(settings.client_id).toBe('exampleclientid')
  // Must be listed in the app client's CallbackURLs (infra/shared/template.yaml).
  expect(settings.redirect_uri).toBe('http://localhost:5173/auth/callback')
  expect(settings.response_type).toBe('code') // authorization code flow (PKCE is automatic)
  expect(settings.scope).toBe('openid email')
  expect(settings.automaticSilentRenew).toBe(true)
  expect(settings.revokeTokenTypes).toEqual(['refresh_token'])
  expect(settings.metadataSeed?.revocation_endpoint).toBe(`${config.cognitoHostedUiUrl}/oauth2/revoke`)
})

test("sign-out uses Cognito's logout endpoint and returns to a listed logout URL", () => {
  const url = new URL(cognitoLogoutUrl(config, 'http://localhost:5173'))

  expect(url.origin + url.pathname).toBe(`${config.cognitoHostedUiUrl}/logout`)
  expect(url.searchParams.get('client_id')).toBe('exampleclientid')
  expect(url.searchParams.get('logout_uri')).toBe('http://localhost:5173/') // template LogoutUrls
})

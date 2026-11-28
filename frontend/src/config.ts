/**
 * Runtime configuration, read from Vite environment variables at build time.
 *
 * Values come from `.env.local` (gitignored), generated from SSM by
 * scripts/frontend-env.ps1, so no account-specific IDs are committed; `.env.example` lists
 * the names. Only variables prefixed with VITE_ are exposed to the browser; never put
 * secrets in them: everything in a frontend bundle is public.
 */

export interface AppConfig {
  catalogueApiUrl: string
  /** Token issuer (OIDC "authority"); its /.well-known/openid-configuration describes Cognito. */
  cognitoAuthority: string
  cognitoClientId: string
  /** Hosted login page base URL; Cognito's sign-out endpoint (/logout) lives here. */
  cognitoHostedUiUrl: string
}

type Env = Record<string, string | undefined>

const REQUIRED = {
  catalogueApiUrl: 'VITE_CATALOGUE_API_URL',
  cognitoAuthority: 'VITE_COGNITO_AUTHORITY',
  cognitoClientId: 'VITE_COGNITO_CLIENT_ID',
  cognitoHostedUiUrl: 'VITE_COGNITO_HOSTED_UI_URL',
} as const satisfies Record<keyof AppConfig, string>

export class ConfigError extends Error {}

const withoutTrailingSlash = (url: string) => url.replace(/\/+$/, '')

/** Validate the environment; fail loudly at start-up instead of with confusing API errors. */
export function loadConfig(env: Env = import.meta.env): AppConfig {
  const missing = Object.values(REQUIRED).filter((name) => !env[name])
  if (missing.length > 0) {
    throw new ConfigError(
      `Missing ${missing.join(', ')}. Run scripts/frontend-env.ps1 to create frontend/.env.local.`,
    )
  }
  const value = (name: string) => env[name] as string
  return {
    catalogueApiUrl: withoutTrailingSlash(value(REQUIRED.catalogueApiUrl)),
    cognitoAuthority: withoutTrailingSlash(value(REQUIRED.cognitoAuthority)),
    cognitoClientId: value(REQUIRED.cognitoClientId),
    cognitoHostedUiUrl: withoutTrailingSlash(value(REQUIRED.cognitoHostedUiUrl)),
  }
}

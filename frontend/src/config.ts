/**
 * Runtime configuration, read from Vite environment variables at build time.
 *
 * Values come from `.env.local` (gitignored), generated from SSM by
 * scripts/frontend-env.ps1, so no account-specific IDs are committed. Only variables
 * prefixed with VITE_ are exposed to the browser; never put secrets in them: everything in
 * a frontend bundle is public.
 */

export interface AppConfig {
  catalogueApiUrl: string
  cognitoUserPoolId: string
  cognitoAppClientId: string
}

type Env = Record<string, string | undefined>

const REQUIRED = {
  catalogueApiUrl: 'VITE_CATALOGUE_API_URL',
  cognitoUserPoolId: 'VITE_COGNITO_USER_POOL_ID',
  cognitoAppClientId: 'VITE_COGNITO_APP_CLIENT_ID',
} as const satisfies Record<keyof AppConfig, string>

export class ConfigError extends Error {}

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
    catalogueApiUrl: value(REQUIRED.catalogueApiUrl).replace(/\/+$/, ''), // no trailing slash
    cognitoUserPoolId: value(REQUIRED.cognitoUserPoolId),
    cognitoAppClientId: value(REQUIRED.cognitoAppClientId),
  }
}

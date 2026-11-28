/**
 * Typed client for the Catalogue API.
 *
 * `catalogue.schema.ts` is generated from services/catalogue/openapi.yaml (`npm run gen:api`),
 * so paths, parameters, request bodies and responses are checked by the TypeScript compiler:
 * if the backend's spec changes, code using an outdated shape stops compiling.
 */
import createClient, { type Middleware } from 'openapi-fetch'
import type { components, paths } from './catalogue.schema'

export type Event = components['schemas']['EventOut']
export type EventCreate = components['schemas']['EventCreate']
export type EventUpdate = components['schemas']['EventUpdate']
export type EventPage = components['schemas']['EventPage']
export type ApiError = components['schemas']['ErrorResponse']['error']

/** Adds a fresh X-Correlation-Id to every request, so its log lines can be found later. */
export const correlationId: Middleware = {
  onRequest({ request }) {
    request.headers.set('X-Correlation-Id', crypto.randomUUID())
    return request
  },
}

/**
 * Adds `Authorization: Bearer <access token>` when someone is signed in. Public routes
 * (browsing) work without it; API Gateway's JWT authorizer checks it on protected routes.
 * The token is read per request, so a silently refreshed token is picked up immediately.
 */
export function bearerToken(getAccessToken: () => Promise<string | undefined>): Middleware {
  return {
    async onRequest({ request }) {
      const token = await getAccessToken()
      if (token) request.headers.set('Authorization', `Bearer ${token}`)
      return request
    },
  }
}

export function createCatalogueClient(baseUrl: string, ...middleware: Middleware[]) {
  const client = createClient<paths>({ baseUrl })
  client.use(correlationId, ...middleware)
  return client
}

export type CatalogueClient = ReturnType<typeof createCatalogueClient>

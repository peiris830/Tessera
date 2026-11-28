import { bearerToken, createCatalogueClient } from './catalogue'

test('every request carries a fresh correlation ID', async () => {
  const seen: string[] = []
  const fetchStub = async (request: Request) => {
    seen.push(request.headers.get('X-Correlation-Id') ?? '')
    return new Response(JSON.stringify({ status: 'ok', service: 'catalogue' }), {
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const client = createCatalogueClient('https://api.example.test')

  const first = await client.GET('/v1/health', { fetch: fetchStub })
  await client.GET('/v1/health', { fetch: fetchStub })

  expect(first.data).toEqual({ status: 'ok', service: 'catalogue' })
  expect(seen).toHaveLength(2)
  expect(seen[0]).toMatch(/^[0-9a-f-]{36}$/)
  expect(seen[0]).not.toBe(seen[1])
})

test('signed-in requests carry the access token; signed-out ones carry none', async () => {
  const seen: (string | null)[] = []
  const fetchStub = async (request: Request) => {
    seen.push(request.headers.get('Authorization'))
    return new Response('{"items":[],"nextToken":null}', { headers: { 'Content-Type': 'application/json' } })
  }
  let token: string | undefined = 'abc.def.ghi'
  const client = createCatalogueClient('https://api.example.test', bearerToken(async () => token))

  await client.GET('/v1/events', { fetch: fetchStub })
  token = undefined
  await client.GET('/v1/events', { fetch: fetchStub })

  expect(seen).toEqual(['Bearer abc.def.ghi', null])
})
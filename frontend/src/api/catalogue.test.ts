import { createCatalogueClient } from './catalogue'

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

import { screen } from '@testing-library/react'
import { Route, Routes, useLocation } from 'react-router'
import { renderAt } from '../test/render'
import { AuthCallbackPage } from './AuthCallbackPage'

const authState = vi.hoisted(() => ({
  current: { isLoading: false, user: null as unknown, error: undefined as Error | undefined },
}))
vi.mock('react-oidc-context', () => ({ useAuth: () => authState.current }))

function Where() {
  const location = useLocation()
  return <p>at {location.pathname + location.search}</p>
}

function renderCallback() {
  renderAt(
    <Routes>
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="*" element={<Where />} />
    </Routes>,
    '/auth/callback?code=abc&state=xyz',
  )
}

test('after the code exchange the user returns to the page they started from', async () => {
  authState.current = { isLoading: false, user: { state: { returnTo: '/organiser/events/new' } }, error: undefined }
  renderCallback()
  expect(await screen.findByText('at /organiser/events/new')).toBeInTheDocument()
})

test('a tampered return address is ignored', async () => {
  authState.current = { isLoading: false, user: { state: { returnTo: '//evil.example' } }, error: undefined }
  renderCallback()
  expect(await screen.findByText('at /events')).toBeInTheDocument()
})

test('a failed exchange explains itself instead of looping', () => {
  authState.current = { isLoading: false, user: null, error: new Error('invalid_grant') }
  renderCallback()
  expect(screen.getByText("Sign-in didn't complete")).toBeInTheDocument()
  expect(screen.getByText('invalid_grant')).toBeInTheDocument()
})

test('while the exchange runs it shows progress', () => {
  authState.current = { isLoading: true, user: null, error: undefined }
  renderCallback()
  expect(screen.getByText('Signing you in…')).toBeInTheDocument()
})

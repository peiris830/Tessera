import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../app/App'
import { attendee, fakeSession, organiser, renderAt } from '../test/render'

test('signed-out visitors can browse, see a Sign in button and no organiser link', async () => {
  const user = userEvent.setup()
  const { session } = renderAt(<App />, '/events')

  expect(screen.getByRole('heading', { name: 'Upcoming events' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'My events' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(session.signIn).toHaveBeenCalledOnce()
})

test('the privacy note explains what happens to an email address', async () => {
  const user = userEvent.setup()
  renderAt(<App />, '/events')

  await user.click(screen.getByRole('button', { name: 'About accounts and privacy' }))
  expect(await screen.findByText(/store your email only to sign you in/)).toBeInTheDocument()
})

test('organisers see My events and an account menu with their role and sign out', async () => {
  const user = userEvent.setup()
  const { session } = renderAt(<App />, '/events', organiser())

  expect(screen.getAllByRole('link', { name: 'My events' }).length).toBeGreaterThan(0)
  expect(screen.queryByRole('button', { name: 'Sign in' })).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Account menu' }))
  expect(await screen.findByText('organiser1@example.com')).toBeInTheDocument()
  expect(screen.getByText('Organiser')).toBeInTheDocument()
  await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))
  expect(session.signOut).toHaveBeenCalledOnce()
})

test('attendees are signed in but get no organiser link', () => {
  renderAt(<App />, '/events', attendee())

  expect(screen.getByRole('button', { name: 'Account menu' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'My events' })).not.toBeInTheDocument()
})

test('a signed-out visit to an organiser page offers sign-in and returns there', async () => {
  const user = userEvent.setup()
  const { session } = renderAt(<App />, '/organiser/events')

  expect(screen.getByRole('heading', { name: 'Sign in to manage your events' })).toBeInTheDocument()
  const panelButtons = screen.getAllByRole('button', { name: 'Sign in' })
  await user.click(panelButtons[panelButtons.length - 1]!)
  expect(session.signIn).toHaveBeenCalledWith() // defaults to the current page
})

test('an attendee visiting an organiser page is told it is for organisers only', () => {
  renderAt(<App />, '/organiser/events/new', attendee())

  expect(screen.getByRole('heading', { name: 'Organisers only' })).toBeInTheDocument()
  expect(screen.getByText(/attendee1@example.com/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Create draft' })).not.toBeInTheDocument()
})

test('while the session is being checked, organiser pages wait instead of flashing a panel', () => {
  renderAt(<App />, '/organiser/events', fakeSession(undefined, 'loading'))

  expect(screen.getByLabelText('Checking your session')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Organisers only' })).not.toBeInTheDocument()
})

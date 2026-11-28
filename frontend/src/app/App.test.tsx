import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderAt } from '../test/render'
import App from './App'

test('the home page redirects to upcoming events with a useful placeholder pane', async () => {
  renderAt(<App />, '/')
  expect(await screen.findByRole('heading', { name: 'Upcoming events' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /upcoming events$/, level: 2 })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Tessera home' })).toBeInTheDocument()
})

test('selecting an event shows its details in the split view', async () => {
  const user = userEvent.setup()
  renderAt(<App />, '/events')
  await user.click(screen.getByRole('button', { name: /Summer Jazz Night/ }))
  expect(screen.getByRole('heading', { name: 'Summer Jazz Night', level: 1 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Reserve/ })).toBeDisabled()
})

test('search filters the event list', async () => {
  const user = userEvent.setup()
  renderAt(<App />, '/events')
  await user.type(screen.getByLabelText('Search events'), 'quartet')
  expect(screen.getByRole('button', { name: /String Quartet/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Summer Jazz Night/ })).not.toBeInTheDocument()
})

test('organisers cannot edit cancelled events and can only publish drafts', async () => {
  renderAt(<App />, '/organiser/events')
  const cancelled = screen.getByText('Spring Brass Matinee').closest('tr')!
  expect(within(cancelled).queryByRole('button', { name: /Edit/ })).not.toBeInTheDocument()
  const published = screen.getByText('Summer Jazz Night').closest('tr')!
  expect(within(published).queryByRole('button', { name: /Publish/ })).not.toBeInTheDocument()
  const draft = screen.getByText('Winter Choral Gala').closest('tr')!
  expect(within(draft).getByRole('button', { name: /Publish/ })).toBeInTheDocument()
})

test('editing a published event locks capacity', async () => {
  renderAt(<App />, '/organiser/events/sample-1')
  expect(await screen.findByRole('heading', { name: 'Edit event' })).toBeInTheDocument()
  expect(screen.getByLabelText(/^Capacity/, { selector: 'input' })).toBeDisabled()
  expect(screen.getByLabelText('Capacity locked')).toBeInTheDocument()
})

test('the create form reports invalid input', async () => {
  const user = userEvent.setup()
  renderAt(<App />, '/organiser/events/new')
  await user.click(await screen.findByRole('button', { name: 'Create draft' }))
  expect(screen.getByText('Title is required')).toBeInTheDocument()
  expect(screen.getByText('Start date and time must be in the future')).toBeInTheDocument()
})

test('unknown routes show a 404 page', () => {
  renderAt(<App />, '/no/such/page')
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
})

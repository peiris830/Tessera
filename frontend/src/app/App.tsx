import { Navigate, Route, Routes } from 'react-router'
import { AuthCallbackPage } from '../auth/AuthCallbackPage'
import { RequireOrganiser } from '../auth/RequireOrganiser'
import { NotFoundPage } from '../features/errors/NotFoundPage'
import { BrowseEventsPage } from '../features/events/BrowseEventsPage'
import { MyEventsPage } from '../features/organiser/MyEventsPage'
import { Shell } from './Shell'

/**
 * Routes. The selected item is part of the URL (/events/:eventId), so the split view's detail
 * pane survives refresh, can be linked to and works with the back button.
 */
export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Navigate to="/events" replace />} />
        <Route path="events" element={<BrowseEventsPage />} />
        <Route path="events/:eventId" element={<BrowseEventsPage />} />
        <Route path="auth/callback" element={<AuthCallbackPage />} />
        <Route element={<RequireOrganiser />}>
          <Route path="organiser/events" element={<MyEventsPage />} />
          <Route path="organiser/events/new" element={<MyEventsPage />} />
          <Route path="organiser/events/:eventId" element={<MyEventsPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { theme } from './theme'

/**
 * App-wide providers: Mantine (theme, light/dark), TanStack Query (server-data cache) and
 * toast notifications. The router is added by the caller (BrowserRouter in main.tsx,
 * MemoryRouter in tests).
 */
export function AppProviders({ children }: { children: ReactNode }) {
  // One cache per app instance (created once, not on every render).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
      }),
  )

  return (
    <MantineProvider theme={theme} defaultColorScheme="auto">
      <QueryClientProvider client={queryClient}>
        <Notifications position="top-right" />
        {children}
      </QueryClientProvider>
    </MantineProvider>
  )
}

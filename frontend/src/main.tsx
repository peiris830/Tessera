// Fonts are self-hosted from npm (@fontsource), so no request goes to Google Fonts.
import '@fontsource/plus-jakarta-sans/400.css'
import '@fontsource/plus-jakarta-sans/500.css'
import '@fontsource/plus-jakarta-sans/600.css'
import '@fontsource/plus-jakarta-sans/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@mantine/core/styles.css'
import '@mantine/dates/styles.css'
import '@mantine/notifications/styles.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './app/App'
import { AppProviders } from './app/AppProviders'
import { OidcSessionProvider } from './auth/OidcSessionProvider'
import { ConfigError, loadConfig } from './config'

const root = createRoot(document.getElementById('root')!)

try {
  const config = loadConfig()
  root.render(
    <StrictMode>
      <BrowserRouter>
        <AppProviders>
          <OidcSessionProvider config={config}>
            <App />
          </OidcSessionProvider>
        </AppProviders>
      </BrowserRouter>
    </StrictMode>,
  )
} catch (error) {
  if (!(error instanceof ConfigError)) throw error
  // Missing .env.local: say exactly what to do instead of showing a blank page.
  root.render(<pre style={{ padding: 16, whiteSpace: 'pre-wrap' }}>{error.message}</pre>)
}

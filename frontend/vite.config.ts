import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/  ·  https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true }, // fixed port: the API's CORS allow-list names it
  test: {
    environment: 'jsdom', // a simulated browser DOM for component tests
    globals: true, // test/expect without imports
    setupFiles: ['./src/test/setup.ts'],
  },
})

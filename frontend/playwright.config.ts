import { defineConfig, devices } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const accountDb = join(
  mkdtempSync(join(tmpdir(), 'frame-browser-')),
  'accounts.db',
)
const apiPort = process.env.PLOTSPOT_E2E_API_PORT ?? '8000'
const webPort = process.env.PLOTSPOT_E2E_WEB_PORT ?? '5173'
const apiOrigin = `http://127.0.0.1:${apiPort}`
const webOrigin = `http://127.0.0.1:${webPort}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: { baseURL: webOrigin, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `../backend/.venv/bin/uvicorn movie_companion.main:app --app-dir ../backend/src --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiOrigin}/api/health`,
      reuseExistingServer: false,
      env: {
        MOVIE_DATA_SOURCE: 'demo',
        TMDB_READ_TOKEN: '',
        FRAME_ACCOUNT_DB: accountDb,
        FRAME_APP_ORIGIN: webOrigin,
        PLOTSPOT_VERIFICATION_MODE: 'preview',
      },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: webOrigin,
      reuseExistingServer: false,
      env: {
        MOVIE_API_TARGET: apiOrigin,
        VITE_PLOTSPOT_LAB_ENABLED: 'true',
      },
    },
  ],
})

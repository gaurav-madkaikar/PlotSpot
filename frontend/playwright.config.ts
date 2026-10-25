import { defineConfig, devices } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const accountDb = join(
  mkdtempSync(join(tmpdir(), 'frame-browser-')),
  'accounts.db',
)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command:
        '../backend/.venv/bin/uvicorn movie_companion.main:app --app-dir ../backend/src --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      env: {
        MOVIE_DATA_SOURCE: 'demo',
        TMDB_READ_TOKEN: '',
        FRAME_ACCOUNT_DB: accountDb,
        FRAME_APP_ORIGIN: 'http://127.0.0.1:5173',
        PLOTSPOT_VERIFICATION_MODE: 'preview',
      },
    },
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      env: { VITE_PLOTSPOT_LAB_ENABLED: 'true' },
    },
  ],
})

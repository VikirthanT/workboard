import { defineConfig } from '@playwright/test';

// Run through `make e2e` (scripts/test_all.py e2e): it builds a throwaway database with the demo world, sets
// DATABASE_URL and DEV_AUTH for the API below, and drops the database afterwards. Ports differ from `make dev`
// (8000 / 5173) so both can run at once.
const API = 'http://127.0.0.1:8100';
const WEB = 'http://127.0.0.1:5174';

export default defineConfig({
  testDir: 'e2e',
  workers: 1, // the specs share one demo database
  retries: 0,
  reporter: [['list'], ...(process.env.WB_E2E_JSON ? [['json', { outputFile: process.env.WB_E2E_JSON }] as const] : [])],
  use: { baseURL: WEB, trace: 'retain-on-failure' },
  webServer: [
    {
      command: '.venv/bin/uvicorn main:app --port 8100',
      cwd: '../server',
      url: `${API}/api/health`,
      env: { ...process.env, DEV_AUTH: 'true', TZ: 'Asia/Kolkata' } as Record<string, string>,
      reuseExistingServer: false,
    },
    {
      command: 'npx vite --port 5174 --strictPort',
      url: WEB,
      env: { ...process.env, WB_API_URL: API } as Record<string, string>,
      reuseExistingServer: false,
    },
  ],
});

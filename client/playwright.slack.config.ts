import { defineConfig } from '@playwright/test';
import { homedir } from 'node:os';
import { join } from 'node:path';

// The Slack walkthrough: the Workboard and the real Slack workspace in one recording. Run through scripts/walkthrough_slack.py,
// which gives the run a throwaway database, starts the Slack listener on it, and publishes into deliverables/slack/.
// Same ports as the other tours (8100 / 5174), so do not run them at once. Slack is opened with the session saved by
// walkthrough/slack-login.mjs (or copied from Firefox); the file is outside the repo.
const API = 'http://127.0.0.1:8100';
const WEB = 'http://127.0.0.1:5174';
const VIEWPORT = { width: Number(process.env.WT_WIDTH ?? 1920), height: Number(process.env.WT_HEIGHT ?? 1080) };
const SLACK_STATE = process.env.WALK_SLACK_STATE ?? join(homedir(), '.cache', 'workboard-walkthrough', 'slack-state.json');

export default defineConfig({
  testDir: 'walkthrough',
  testMatch: 'slack.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 10 * 60_000,
  reporter: [['list']],
  use: { baseURL: WEB, trace: 'off', storageState: SLACK_STATE },
  projects: [
    { name: 'screenshots', use: { viewport: VIEWPORT, deviceScaleFactor: 1.5 } },
    { name: 'video', use: { viewport: VIEWPORT, video: { mode: 'on', size: VIEWPORT } } },
  ],
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

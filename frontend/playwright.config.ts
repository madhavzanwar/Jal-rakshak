import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

/**
 * E2E against the GitHub Pages demo build (vite preview of `npm run build:demo`).
 * Until the backend has generated public/demo/scenario.json, fall back to the dev server
 * in demo mode, which serves the small hand-written fixture.
 */
const hasScenario = existsSync('public/demo/scenario.json');
const base = '/Jal-rakshak/';
const port = hasScenario ? 4173 : 5180;
const baseURL = `http://localhost:${port}${hasScenario ? base : '/'}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL,
    trace: 'off',
    serviceWorkers: 'block',
    viewport: { width: 1440, height: 900 },
    ...(process.env.PW_CHROMIUM_PATH ? { launchOptions: { executablePath: process.env.PW_CHROMIUM_PATH } } : {}),
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: hasScenario
    ? {
        command: `npm run build:demo && npx vite preview --port ${port} --strictPort --base ${base}`,
        url: baseURL,
        timeout: 240_000,
        reuseExistingServer: !process.env.CI,
        env: { VITE_BASE: base },
      }
    : {
        command: `npx vite --port ${port} --strictPort`,
        url: baseURL,
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
        env: { VITE_DEMO: '1' },
      },
});

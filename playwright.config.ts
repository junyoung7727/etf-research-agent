import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8018',
    viewport: { width: 402, height: 874 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `${process.platform === 'win32' ? '.venv/Scripts/python' : '.venv/bin/python'} -m uvicorn server.app:app --host 127.0.0.1 --port 8018`,
    url: 'http://127.0.0.1:8018/api/health',
    reuseExistingServer: !process.env.CI,
  },
})

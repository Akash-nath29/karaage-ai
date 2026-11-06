import { defineConfig } from '@playwright/test'

const python = process.platform === 'win32' ? '..\\.venv\\Scripts\\python.exe' : '../.venv/bin/python'

// Runs against the real stack: Vite → FastAPI → Postgres (start the db with docker compose first).
export default defineConfig({
  testDir: 'e2e',
  use: { baseURL: 'http://127.0.0.1:5173' },
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
    },
  ],
})

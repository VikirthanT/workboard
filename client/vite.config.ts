import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // In development the app's /api calls go to the API that `make dev` starts.
  // WB_API_URL lets the end-to-end tests (make e2e) point at their own API beside a running `make dev`.
  server: { proxy: { '/api': process.env.WB_API_URL ?? 'http://127.0.0.1:8000' } },
});

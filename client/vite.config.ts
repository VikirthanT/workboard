import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // In development the app's /api calls go to the API that `make dev` starts.
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
});

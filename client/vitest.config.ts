import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Separate from vite.config.ts so tests do not load the Tailwind plugin.
export default defineConfig({
  plugins: [react()],
  // maxForks keeps vitest from starting one worker per core (14 here) and starving the laptop.
  test: { environment: 'jsdom', globals: false, include: ['src/**/*.test.{ts,tsx}'], setupFiles: ['src/test/setup.ts'], poolOptions: { forks: { maxForks: 4 } } },
});

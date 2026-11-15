import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Separate from vite.config.ts so tests do not load the Tailwind plugin.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
    // maxWorkers keeps vitest from starting one worker per core (14 here) and starving the laptop.
    // (Vitest 4 replaced poolOptions.forks.maxForks with this top-level option.)
    maxWorkers: 4,
  },
});

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Polling, and only when asked for. A bind mount from a Windows host into a Linux container
  // delivers no filesystem events, so the watcher hears nothing and a save never reaches the
  // browser — the failure looks like HMR being broken rather than like a mount being quiet.
  // Polling costs a wakeup per interval per file, which is a bad trade for anyone running
  // `npm run dev` directly, so docker-compose.yaml sets VITE_USE_POLLING and nothing else does.
  server: process.env.VITE_USE_POLLING ? { watch: { usePolling: true, interval: 300 } } : {},
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
  },
})

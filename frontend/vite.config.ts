import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config with a single default export. Proxy `/api` during local dev to Django on port 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})

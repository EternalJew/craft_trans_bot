import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // The landing page owns "/", so the dashboard lives under /admin
  base: '/admin/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0', // Allow external connections in Docker
    open: false, // Don't auto-open browser in Docker
  },
  // Environment variables prefixed with VITE_ are exposed to the client
  // VITE_API_BASE_URL will be available via import.meta.env.VITE_API_BASE_URL
  envPrefix: 'VITE_',
})



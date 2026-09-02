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
    proxy: {
      '/api': {
        target: 'http://localhost:8999',
        changeOrigin: true,
      },
      '/booking': {
        target: 'http://localhost:8999',
        changeOrigin: true,
      },
      '/control': {
        target: 'http://localhost:8999',
        changeOrigin: true,
      },
    },
    // 允許 ngrok 域名做 host check
    host: true,
    allowedHosts: ['.ngrok.io'],
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // 本機啟動腳本將 SnowLand 的公開 OAuth Client ID 放在專案根目錄 .env.local。
  envDir: path.resolve(__dirname, '..'),
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8999',
        changeOrigin: true,
      },
      '/booking': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8999',
        changeOrigin: true,
      },
      '/control': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8999',
        changeOrigin: true,
      },
    },
    // 允許 ngrok 域名做 host check
    host: true,
    allowedHosts: ['.ngrok.io'],
  },
})

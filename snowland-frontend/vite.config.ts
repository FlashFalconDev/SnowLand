import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { existsSync } from 'node:fs'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Preserve existing installations until their VITE_ settings are moved.
  const hasFrontendEnv = ['.env', '.env.local', `.env.${mode}`, `.env.${mode}.local`]
    .some(name => existsSync(path.join(__dirname, name)))
  const envDir = hasFrontendEnv ? __dirname : path.resolve(__dirname, '..')
  const env = loadEnv(mode, envDir, 'VITE_')
  const apiTarget = process.env.VITE_API_TARGET || env.VITE_API_TARGET || 'http://127.0.0.1:8999'
  return {
    plugins: [react()],
    // 優先讀取前端設定；沒有前端設定檔時相容舊版根目錄設定。
    envDir,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/booking': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/control': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
      // 允許 ngrok 域名做 host check
      host: true,
      allowedHosts: ['.ngrok.io'],
    },
  }
})

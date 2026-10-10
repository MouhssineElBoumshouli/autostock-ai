import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'

const projectDirectory = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectDirectory, '')
  const odooTarget = env.ODOO_PROXY_TARGET || 'http://127.0.0.1:8177'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': path.resolve(projectDirectory, 'src') },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/autostock/api': { target: odooTarget, changeOrigin: true },
        '/web': { target: odooTarget, changeOrigin: true },
      },
    },
    test: {
      environment: 'node',
      include: ['src/**/*.test.{ts,tsx}', 'tests/**/*.test.ts'],
      restoreMocks: true,
      clearMocks: true,
    },
  }
})

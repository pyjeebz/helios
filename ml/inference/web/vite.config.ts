import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      // Rewrite /api/v1/* to /* for ML endpoints (predict, detect, recommend)
      '/api/v1': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1/, '')
      },
      // Keep /api/* as-is for deployments, agents endpoints
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true
        // No rewrite - backend expects /api/deployments, /api/metrics, etc.
      }
    }
  },
  build: {
    outDir: '../static',
    emptyOutDir: true
  }
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss()
  ],
  server: {
    port: 5173,
    proxy: {
      // Proxy all /api requests to the Frappe server.
      // This enables same-origin cookies (session, csrf_token) to work
      // seamlessly between the Vite dev server and Frappe backend.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        // Forward cookies through the proxy
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // Forward the Cookie header so Frappe session works
            if (req.headers.cookie) {
              proxyReq.setHeader('Cookie', req.headers.cookie)
            }
          })
        }
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})

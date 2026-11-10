import { defineConfig, loadEnv } from 'vite'

// Node-only configuration, based on the pinned B2 proxy example.
export default defineConfig(({ command, mode }) => {
  if (command !== 'serve') return {}

  const serverEnv = loadEnv(mode, process.cwd(), 'TRACE_')
  const apiKey = process.env.TRACE_API_KEY || serverEnv.TRACE_API_KEY
  const target = process.env.TRACE_API_TARGET || serverEnv.TRACE_API_TARGET || 'http://127.0.0.1:8000'
  if (!apiKey) throw new Error('TRACE_API_KEY is required by the server-side Vite proxy')

  return {
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api/v1': {
          target,
          changeOrigin: true,
          configure(proxy) {
            proxy.on('proxyReq', (proxyReq) => {
              // A browser-supplied credential must never override the server key.
              proxyReq.setHeader('X-API-Key', apiKey)
            })
          },
        },
      },
    },
  }
})

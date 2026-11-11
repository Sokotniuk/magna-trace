import { defineConfig, loadEnv } from 'vite'

// Node-only configuration, based on the pinned B2 proxy example.
export default defineConfig(({ command, mode }) => {
  const publicEnv = loadEnv(mode, process.cwd(), 'VITE_TRACE_API_MODE')
  const apiMode = process.env.VITE_TRACE_API_MODE ?? publicEnv.VITE_TRACE_API_MODE ?? 'mock'
  if (!['mock', 'live'].includes(apiMode)) throw new Error('VITE_TRACE_API_MODE must be mock or live')
  const modeConfig = { define: { 'import.meta.env.VITE_TRACE_API_MODE': JSON.stringify(apiMode) } }
  if (command !== 'serve') return modeConfig

  const serverEnv = loadEnv(mode, process.cwd(), 'TRACE_')
  const apiKey = process.env.TRACE_API_KEY || serverEnv.TRACE_API_KEY
  const target = process.env.TRACE_API_TARGET || serverEnv.TRACE_API_TARGET || 'http://127.0.0.1:8000'
  if (!apiKey) throw new Error('TRACE_API_KEY is required by the server-side Vite proxy')

  return {
    ...modeConfig,
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

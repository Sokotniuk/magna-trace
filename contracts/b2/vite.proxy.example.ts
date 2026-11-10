// Reference configuration for D. Runs in Node; never import into React components.
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const serverEnv = loadEnv(mode, process.cwd(), '');
  const apiKey = process.env.TRACE_API_KEY || serverEnv.TRACE_API_KEY;
  const target = process.env.TRACE_API_TARGET || serverEnv.TRACE_API_TARGET || 'http://127.0.0.1:8000';
  if (!apiKey) throw new Error('TRACE_API_KEY is required by the server-side Vite proxy');
  return {
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api/v1': {
          target,
          changeOrigin: true,
          configure(proxy) {
            proxy.on('proxyReq', (proxyReq) => {
              // Always overwrite a browser-supplied key with the server-held key.
              proxyReq.setHeader('X-API-Key', apiKey);
            });
          },
        },
      },
    },
  };
});

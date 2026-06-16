import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'sse-timeout-fix',
      configureServer(server) {
        // Node.js HTTP server has a default 2-minute inactivity timeout
        // that kills SSE connections (browser never sends data after the
        // initial GET, so the socket appears "inactive" to Node).
        server.httpServer?.setTimeout(0);
      },
    },
  ],
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
    port: 5777,
    proxy: {
      '/api': {
        target: 'http://localhost:8777',
        changeOrigin: true,
        // SSE support: disable buffering & socket timeout
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Disable Node.js socket timeout on both sides of the proxy
            // for SSE endpoints.  req.socket = browser→Vite,
            // proxyReq.socket = Vite→backend.  Without this the OS /
            // Node.js default timeout kills the connection after ~2 min.
            if (req.url?.includes('index/status') || req.url?.includes('search/stream')) {
              req.socket?.setTimeout(0);
              proxyReq.on('socket', (socket) => {
                socket.setTimeout(0);
              });
            }
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // Disable buffering for SSE endpoints
            if (req.url?.includes('/events') || proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache';
              proxyRes.headers['x-accel-buffering'] = 'no';
              res.flushHeaders();
            }
          });
        },
      },
    },
  },
})

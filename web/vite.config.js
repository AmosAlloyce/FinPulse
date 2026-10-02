import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  base: '/finpulse/',
  server: {
    proxy: {
      '/finpulse/api': {
        target: 'http://127.0.0.1:8011',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/finpulse/, ''),
      },
    },
  },
});

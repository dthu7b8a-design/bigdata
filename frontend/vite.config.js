import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
export default defineConfig({
  plugins: [vue()],
  // The published DataV package points module to index.js but ships index.mjs.
  resolve: { alias: [{ find: /^@dataview\/datav-vue3$/, replacement: fileURLToPath(new URL('./node_modules/@dataview/datav-vue3/es/index.mjs', import.meta.url)) }] },
  server: { port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true } } },
  preview: { port: 4173, proxy: { '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true } } },
  build: { outDir: 'dist', rollupOptions: { output: { manualChunks: { charts: ['echarts/core'], vue: ['vue'], datav: ['@dataview/datav-vue3'] } } } }
})

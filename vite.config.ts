import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { rolldownOptions: { input: { main: 'index.html', original: 'original.html' } } },
  server: { proxy: { '/api': 'http://127.0.0.1:8018' } },
})

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The FastAPI backend (uvicorn app.main:create_app --factory) serves /api on port 8000.
    proxy: { '/api': 'http://localhost:8000' },
  },
})

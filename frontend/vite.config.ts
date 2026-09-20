import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Configuration comes from the environment only (frontend/.env or real environment variables), with no
  // fallback in the code: a missing value stops the dev server / build here, instead of shipping a bundle
  // that points at the wrong API.
  // '.' is the folder Vite runs from (frontend/); loadEnv also picks up real environment variables.
  const env = loadEnv(mode, '.', 'VITE_')
  if (!env.VITE_API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL is not set. Add it to frontend/.env (see .env.example) or export it before building.')
  }
  return { plugins: [react()] }
})

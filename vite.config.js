import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages는 /D-MIN-prototype/ 아래에서 서비스되므로 상대 경로로 빌드한다.
// 실시간 AIS 모드: 개발 서버가 /api를 로컬 demo 서버(make serve, 8000)로 넘긴다. 키는 그 서버에만 있다.
export default defineConfig({
  base: './',
  plugins: [vue()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } } },
})

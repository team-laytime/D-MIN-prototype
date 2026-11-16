import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 상대 경로로 빌드한다: 같은 결과물이 GitHub Pages(/D-MIN-prototype/ 아래, 서버 없음)와
// Compose의 nginx(/ 아래, /api는 Caddy가 Spring으로) 양쪽에서 그대로 돈다.
// 개발 서버(npm run dev)는 /api를 로컬 입구 Caddy(127.0.0.1:18089)로 넘긴다.
export default defineConfig({
  base: './',
  plugins: [vue()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:18089', changeOrigin: false } } },
})

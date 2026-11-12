import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages는 /D-MIN-prototype/ 아래에서 서비스되므로 상대 경로로 빌드한다.
export default defineConfig({ base: './', plugins: [vue()] })

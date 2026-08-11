import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 指南坑点预警：手机调试时 axios 不能写死 localhost。
// 统一用相对路径 /api + vite proxy 转发到后端，手机连同一 WiFi 也能通。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true, // 开放局域网访问（等价于 vite --host）
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 指南坑点预警：手机调试时 axios 不能写死 localhost。
// 统一用相对路径 /api + vite proxy 转发到后端，手机连同一 WiFi 也能通。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true, // 开放局域网访问（等价于 vite --host）
    // Windows 下原生 fs 监听遇临时文件/重命名会 EBUSY 崩溃（AI 编辑工具的原子写触发过），
    // 改用轮询监听：牺牲一点实时性，换开发期稳定。
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
// 样式顺序：Element 基础样式 → 设计令牌 → Element 主题覆盖 → 全局样式
import './styles/tokens.css'
import './styles/element-overrides.css'
import './style.css'

import App from './App.vue'
import router from './router'

// 主题尽早应用，避免首屏闪白：优先用户选择，其次跟随系统
const savedTheme = localStorage.getItem('labx_theme')
const wantDark = savedTheme === 'dark' || (savedTheme === null && window.matchMedia('(prefers-color-scheme: dark)').matches)
if (wantDark) document.documentElement.dataset.theme = 'dark'

createApp(App).use(router).use(ElementPlus, { locale: zhCn }).mount('#app')

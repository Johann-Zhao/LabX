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

createApp(App).use(router).use(ElementPlus, { locale: zhCn }).mount('#app')

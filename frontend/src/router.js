import { createRouter, createWebHistory } from 'vue-router'

import AdminPage from './views/AdminPage.vue'
import AskPage from './views/AskPage.vue'
import BorrowResult from './views/BorrowResult.vue'
import CardPage from './views/CardPage.vue'
import LoginPage from './views/LoginPage.vue'
import MaterialDetail from './views/MaterialDetail.vue'
import MaterialList from './views/MaterialList.vue'
import RecordsPage from './views/RecordsPage.vue'
import { currentUser } from './store'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginPage, meta: { title: '登录', public: true } },
    // 智能助手即首页；物料列表移到 /materials
    { path: '/', name: 'assistant', component: AskPage, meta: { title: '智能助手' } },
    { path: '/materials', name: 'materials', component: MaterialList, meta: { title: '物料' } },
    { path: '/materials/:id', name: 'material-detail', component: MaterialDetail },
    { path: '/cards/:id', name: 'card-detail', component: CardPage },
    { path: '/borrow/result', name: 'borrow-result', component: BorrowResult },
    { path: '/bom', redirect: '/' }, // 愿望到方案已融合进智能助手对话页
    // 旧对话页地址保留跳转，query（如 material_id）原样带到新首页
    { path: '/ask', redirect: (to) => ({ path: '/', query: to.query }) },
    { path: '/admin', name: 'admin', component: AdminPage, meta: { title: '管理' } },
    { path: '/records', name: 'records', component: RecordsPage, meta: { title: '我的借用' } },
  ],
})

// 全局守卫（登录态 = currentUser.role，见 store.js）：
// - 未登录访问任何非 /login 页 → 跳 /login
// - 已登录访问 /login → 按 role 回各自首页（admin → /admin，student → /）
// - student 访问 /admin → 挡回 /（管理端只对 admin 开放）
router.beforeEach((to) => {
  const role = currentUser.role
  if (to.path === '/login') {
    if (!role) return true
    return role === 'admin' ? '/admin' : '/'
  }
  if (!role) return '/login'
  if (to.path.startsWith('/admin') && role !== 'admin') return '/'
  return true
})

export default router

import { createRouter, createWebHistory } from 'vue-router'

import AdminPage from './views/AdminPage.vue'
import AskPage from './views/AskPage.vue'
import BorrowResult from './views/BorrowResult.vue'
import CardPage from './views/CardPage.vue'
import MaterialDetail from './views/MaterialDetail.vue'
import MaterialList from './views/MaterialList.vue'
import RecordsPage from './views/RecordsPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'materials', component: MaterialList, meta: { title: '物料' } },
    { path: '/materials/:id', name: 'material-detail', component: MaterialDetail },
    { path: '/cards/:id', name: 'card-detail', component: CardPage },
    { path: '/borrow/result', name: 'borrow-result', component: BorrowResult },
    { path: '/bom', redirect: '/ask' }, // 愿望到方案已融合进智能助手对话页
    { path: '/admin', name: 'admin', component: AdminPage, meta: { title: '管理' } },
    { path: '/ask', name: 'ask', component: AskPage, meta: { title: '智能助手' } },
    { path: '/records', name: 'records', component: RecordsPage, meta: { title: '我的借用' } },
  ],
})

export default router

import { createRouter, createWebHistory } from 'vue-router'

import AskPage from './views/AskPage.vue'
import BomPage from './views/BomPage.vue'
import BorrowResult from './views/BorrowResult.vue'
import MaterialDetail from './views/MaterialDetail.vue'
import MaterialList from './views/MaterialList.vue'
import RecordsPage from './views/RecordsPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'materials', component: MaterialList, meta: { title: '物料' } },
    { path: '/materials/:id', name: 'material-detail', component: MaterialDetail },
    { path: '/borrow/result', name: 'borrow-result', component: BorrowResult },
    { path: '/bom', name: 'bom', component: BomPage, meta: { title: '愿望到方案' } },
    { path: '/ask', name: 'ask', component: AskPage, meta: { title: '问答' } },
    { path: '/records', name: 'records', component: RecordsPage, meta: { title: '我的借用' } },
  ],
})

export default router

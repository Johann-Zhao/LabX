import { reactive } from 'vue'

// 当前登录用户。默认小王；顶栏可切换（演示"换个账号"视角）。
// 持久化到 localStorage：整页刷新后身份不变（演示中途刷新不怕掉身份）。
const saved = (() => {
  try {
    return JSON.parse(localStorage.getItem('labx_user'))
  } catch {
    return null
  }
})()

export const currentUser = reactive(saved || { id: '2024001', name: '小王' })

export function setUser(user) {
  currentUser.id = user.id
  currentUser.name = user.name
  localStorage.setItem('labx_user', JSON.stringify({ id: user.id, name: user.name }))
}

// 最近一次借用结果，借用成功页展示用（BorrowResult.vue 读取）
export const lastBorrowResult = reactive({
  record_id: '',
  material_id: '',
  material_name: '',
  due_at: '',
  knowledge_card: null,
})

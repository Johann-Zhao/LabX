import { reactive } from 'vue'

// 当前登录用户（含 role，由登录接口下发）。持久化到 localStorage：整页刷新不掉登录态。
// 登录功能上线前的"默认小王"兜底已移除——无 role 的旧存档一律视为未登录，路由守卫挡去 /login。
const saved = (() => {
  try {
    const u = JSON.parse(localStorage.getItem('labx_user'))
    return u && u.role ? u : null
  } catch {
    return null
  }
})()

export const currentUser = reactive(saved || { id: '', name: '', role: '' })

export function setUser(user) {
  currentUser.id = user.id
  currentUser.name = user.name
  currentUser.role = user.role
  localStorage.setItem('labx_user', JSON.stringify({ id: user.id, name: user.name, role: user.role }))
}

// 退出登录：清存档 + 重置状态（跳转 /login 由调用方做）
export function logout() {
  currentUser.id = ''
  currentUser.name = ''
  currentUser.role = ''
  localStorage.removeItem('labx_user')
}

// 最近一次借用结果，借用成功页展示用（BorrowResult.vue 读取）
export const lastBorrowResult = reactive({
  record_id: '',
  material_id: '',
  material_name: '',
  due_at: '',
  knowledge_card: null,
})

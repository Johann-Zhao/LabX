import { reactive } from 'vue'

// 当前登录用户。阶段 1 先写死（登录与切换账号在阶段 3 做）；
// 2024001 小王 / 2024002 小李 是 init_db.py 灌入的测试用户。
export const currentUser = reactive({ id: '2024001', name: '小王' })

// 最近一次借用结果，借用成功页展示用（BorrowResult.vue 读取）
export const lastBorrowResult = reactive({
  record_id: '',
  material_id: '',
  material_name: '',
  due_at: '',
  knowledge_card: null,
})

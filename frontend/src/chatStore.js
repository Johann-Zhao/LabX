// 对话持久化仓库：按账号分存，localStorage 落盘。
// 作用：同一账号的智能助手对话跨页面切换 / 整页刷新 / 重新登录都不丢；
//      提供多会话（新会话、历史切换），避免上下文污染。
import { computed, ref } from 'vue'
import { currentUser } from './store'

const STORAGE_KEY = 'labx_chat_history'

// 读取全部账号的历史：{ [userId]: [ {id,title,messages,updatedAt}, ... ] }
function loadAll() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return raw && typeof raw === 'object' ? raw : {}
  } catch {
    return {}
  }
}

const all = ref(loadAll())
// 当前正在聊的会话 ID（进程内状态：切页面/刷新后由 ensureConversation 恢复为最近一个会话）
const currentConvId = ref('')

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all.value))
  } catch {
    /* 存储写不进（隐私模式等）就只保留内存态 */
  }
}

function userKey() {
  return currentUser.id || 'guest'
}

// 当前账号的会话列表（新会话在前，按 updatedAt 倒序）
export const conversations = computed(() => all.value[userKey()] || [])

// 页面挂载时调用：恢复上次会话，或新建一个
export function ensureConversation() {
  const list = conversations.value
  if (currentConvId.value && list.some((c) => c.id === currentConvId.value)) return
  if (list.length > 0) {
    currentConvId.value = list[0].id
    return
  }
  newConversation()
}

export function currentConversation() {
  return conversations.value.find((c) => c.id === currentConvId.value) || null
}

export function currentId() {
  return currentConvId.value
}

// 开新会话：空对话、空标题，置顶
export function newConversation() {
  const conv = { id: `conv-${Date.now()}`, title: '', messages: [], updatedAt: Date.now() }
  all.value[userKey()] = [conv, ...conversations.value]
  currentConvId.value = conv.id
  persist()
  return conv
}

export function switchConversation(id) {
  if (conversations.value.some((c) => c.id === id)) {
    currentConvId.value = id
  }
}

// 追加一条消息（用户/助手共用）；首个用户消息自动做会话标题（前 20 字）
export function appendMessage(msg) {
  const conv = currentConversation()
  if (!conv) return
  conv.messages.push(msg)
  if (!conv.title && msg.role === 'user') conv.title = String(msg.text || '').slice(0, 20)
  conv.updatedAt = Date.now()
  persist()
}

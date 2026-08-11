import axios from 'axios'

// 统一走相对路径 /api，由 vite proxy 转发到后端（AGENTS.md 第 5 节：禁止写死 localhost）
const http = axios.create({ baseURL: '/api', timeout: 10000 })

// 以下函数都返回完整响应体 { code, msg, data }，由页面根据 code 分支处理

export async function fetchMaterials(keyword = '', category = '') {
  const { data } = await http.get('/materials', { params: { keyword, category } })
  return data
}

export async function fetchMaterial(materialId) {
  const { data } = await http.get(`/materials/${materialId}`)
  return data
}

export async function borrowMaterial(userId, materialId) {
  const { data } = await http.post('/borrow', { user_id: userId, material_id: materialId })
  return data
}

export async function returnMaterial(recordId) {
  const { data } = await http.post('/return', { record_id: recordId })
  return data
}

export async function fetchRecords(userId = '') {
  const { data } = await http.get('/records', { params: { user_id: userId } })
  return data
}

// RAG 问答。materialId 可空——传入则限定该物料的知识上下文（数字分身对话窗）
export async function askQuestion(question, materialId = null) {
  const { data } = await http.post('/ask', { question, material_id: materialId })
  return data
}

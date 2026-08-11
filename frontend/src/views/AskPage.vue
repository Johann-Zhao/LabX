<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentChat, askQuestion, fetchMaterial } from '../api'
import { currentUser } from '../store'

const route = useRoute()
const materialId = route.query.material_id || null // 从物料详情页进入时带上（数字分身对话窗）
const materialName = ref('')

// { role: 'user'|'assistant', text, refs: [{card_id,title}], steps: [{step,detail}] }
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const listRef = ref(null)
const expandedSteps = ref({}) // 每条消息的"协作过程"展开状态

onMounted(async () => {
  if (materialId) {
    const res = await fetchMaterial(materialId)
    if (res.code === 0) materialName.value = res.data.name
    messages.value.push({
      role: 'assistant',
      text: `你好，我是${materialName.value || '这件物料'}的专属助教。关于它的接线、用法、踩坑，都可以问我。`,
      refs: [],
      steps: [],
    })
  } else {
    messages.value.push({
      role: 'assistant',
      text: '你好，我是 LabX 智能助手。可以说"我的电机不转"让我排障，也可以说"我想做自动浇花装置"让我出方案。',
      refs: [],
      steps: [],
    })
  }
})

async function send() {
  const question = input.value.trim()
  if (!question || thinking.value) return
  messages.value.push({ role: 'user', text: question, refs: [], steps: [] })
  input.value = ''
  thinking.value = true
  scrollToBottom()
  try {
    // 物料详情页进入 → 限定物料的 RAG 问答；否则走智能体编排（排障/方案/库存/闲聊）
    const res = materialId
      ? await askQuestion(question, materialId)
      : await agentChat(currentUser.id, question)
    if (res.code === 0) {
      messages.value.push({
        role: 'assistant',
        text: res.data.answer,
        refs: res.data.references || [],
        steps: res.data.steps || [],
      })
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    thinking.value = false
    scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: 'smooth' })
}
</script>

<template>
  <div class="ask-page">
    <el-alert
      v-if="materialId"
      type="success"
      :closable="false"
      class="ctx"
      :title="`正在围绕「${materialName || materialId}」提问，回答只参考这件物料的知识`"
    />

    <div ref="listRef" class="msg-list">
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <!-- 智能体协作过程（排障演示的高潮镜头） -->
        <div v-if="m.steps?.length" class="steps" @click="expandedSteps[i] = !expandedSteps[i]">
          <span class="steps-toggle">{{ expandedSteps[i] ? '▾' : '▸' }} 多智能体协作过程（{{ m.steps.length }} 步）</span>
          <div v-show="expandedSteps[i]" class="steps-list">
            <div v-for="(s, j) in m.steps" :key="j" class="step-item">
              <span class="step-name">{{ j + 1 }}. {{ s.step }}</span>
              <span class="step-detail">{{ s.detail }}</span>
            </div>
          </div>
        </div>
        <div class="bubble">{{ m.text }}</div>
        <div v-if="m.refs?.length" class="refs">
          参考：
          <el-tag v-for="r in m.refs" :key="r.card_id" size="small" class="ref-tag">{{ r.title }}</el-tag>
        </div>
      </div>
      <div v-if="thinking" class="msg assistant">
        <div class="bubble thinking">正在调用各能力模块协作处理…</div>
      </div>
    </div>

    <div class="input-bar">
      <el-input
        v-model="input"
        placeholder="描述你的问题或想法…"
        size="large"
        :disabled="thinking"
        @keyup.enter="send"
      />
      <el-button type="primary" size="large" :loading="thinking" @click="send">发送</el-button>
    </div>
  </div>
</template>

<style scoped>
.ask-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 180px);
}
.ctx {
  margin-bottom: 8px;
}
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 2px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg {
  display: flex;
  flex-direction: column;
  max-width: 90%;
}
.msg.user {
  align-self: flex-end;
  align-items: flex-end;
}
.msg.assistant {
  align-self: flex-start;
  align-items: flex-start;
}
.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.user .bubble {
  background: #42b883;
  color: #fff;
}
.assistant .bubble {
  background: #fff;
  color: #303133;
  border: 1px solid #ebeef5;
}
.thinking {
  color: #909399;
}
.steps {
  margin-bottom: 4px;
  font-size: 12px;
  color: #909399;
  cursor: pointer;
  user-select: none;
}
.steps-list {
  margin-top: 4px;
  padding: 8px 10px;
  background: #f0f9eb;
  border-left: 3px solid #42b883;
  border-radius: 4px;
}
.step-item {
  display: flex;
  flex-direction: column;
  padding: 3px 0;
}
.step-name {
  color: #42b883;
  font-weight: bold;
}
.step-detail {
  color: #606266;
}
.refs {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
.ref-tag {
  margin: 2px 4px 0 0;
}
.input-bar {
  display: flex;
  gap: 8px;
  padding-top: 8px;
}
</style>

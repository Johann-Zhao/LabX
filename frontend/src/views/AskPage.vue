<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentChatStream, askQuestion, fetchMaterial } from '../api'
import { currentUser } from '../store'
import BomCard from './BomCard.vue'

const route = useRoute()
const materialId = route.query.material_id || null // 从物料详情页进入时带上（数字分身对话窗）
const materialName = ref('')

// 会话 ID：页面生命周期内不变，用于后端挂起/恢复澄清状态（见 docs/agent-workflow.md）
const convId = `conv-${Date.now()}`

// { role, text, refs, steps, provenance, clarify: {options}, bom }
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const listRef = ref(null)
const expandedSteps = ref({})

// 过程显化区（流式）：等待 final 期间逐行显示真实执行状态，最后一行带跳动圆点
const streamLines = ref([])
const streamActive = ref(false)

const PROVENANCE_META = {
  local_kb: { text: '本地知识库', type: 'success' },
  web: { text: '网络检索', type: 'primary' },
  model: { text: '通用经验', type: 'info' },
  offline: { text: '离线兜底', type: 'warning' },
}

onMounted(async () => {
  if (materialId) {
    const res = await fetchMaterial(materialId)
    if (res.code === 0) materialName.value = res.data.name
    messages.value.push({
      role: 'assistant',
      text: `你好，我是${materialName.value || '这件物料'}的专属助教。关于它的接线、用法、踩坑，都可以问我。`,
    })
  } else {
    messages.value.push({
      role: 'assistant',
      text: '你好，我是 LabX 智能助手。可以说"我想做自动浇花装置"让我出方案并一键预约，也可以说"我的电机不转"让我排障——没说清是什么物料时我会先问你。手里有物料不知道怎么用？直接问我"这块板子能做什么"。',
    })
  }
})

async function send() {
  const question = input.value.trim()
  if (!question || thinking.value) return
  await sendText(question)
}

// 点击澄清选项 = 把选项文本作为下一条消息发送（同一会话）
async function sendText(text) {
  messages.value.push({ role: 'user', text })
  input.value = ''
  thinking.value = true
  streamLines.value = []
  streamActive.value = true
  scrollToBottom()
  try {
    // 物料详情页进入 → 限定物料的 RAG 问答；否则走智能体编排（流式过程显化，失败自动回退非流式）
    const res = materialId
      ? await askQuestion(text, materialId)
      : await agentChatStream(currentUser.id, text, convId, (s) => {
          streamLines.value.push(s)
          scrollToBottom()
        })
    streamActive.value = false
    if (res.code === 0) {
      messages.value.push({
        role: 'assistant',
        // 气泡是纯文本渲染（pre-wrap），洗掉 LLM 偶发输出的 markdown 加粗记号
        text: (res.data.answer || '').replace(/\*\*/g, ''),
        refs: res.data.references || [],
        steps: res.data.steps || [],
        provenance: res.data.provenance || null,
        clarify: res.data.clarify || null,
        bom: res.data.bom || null,
      })
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    thinking.value = false
    streamActive.value = false
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

        <div class="bubble">
          {{ m.text }}
          <el-tag
            v-if="m.provenance && PROVENANCE_META[m.provenance]"
            :type="PROVENANCE_META[m.provenance].type"
            size="small"
            class="prov-tag"
          >
            {{ PROVENANCE_META[m.provenance].text }}
          </el-tag>
        </div>

        <!-- 澄清选项：点击即回答 -->
        <div v-if="m.clarify?.options?.length" class="chips">
          <el-button
            v-for="opt in m.clarify.options"
            :key="opt"
            size="small"
            round
            class="chip"
            @click="sendText(opt)"
          >
            {{ opt }}
          </el-button>
        </div>

        <!-- 愿望到方案：BOM 卡片内联（清单一键预约） -->
        <BomCard v-if="m.bom" :bom="m.bom" />

        <div v-if="m.refs?.length" class="refs">
          参考：
          <template v-for="r in m.refs" :key="r.card_id || r.url">
            <el-tag v-if="r.card_id" size="small" class="ref-tag">{{ r.title }}</el-tag>
            <a v-else-if="r.url" :href="r.url" target="_blank" rel="noopener" class="ref-link">{{ r.title }} ↗</a>
          </template>
        </div>
      </div>
      <!-- 过程显化区（流式）：真实执行状态逐行显示，当前行带跳动圆点，final 到达后全部置灰 -->
      <div v-if="thinking" class="msg assistant">
        <div class="stream-proc">
          <template v-if="streamLines.length">
            <div
              v-for="(line, i) in streamLines"
              :key="i"
              :class="['stream-line', { current: streamActive && i === streamLines.length - 1 }]"
            >
              {{ line }}
              <span v-if="streamActive && i === streamLines.length - 1" class="dots"><i /><i /><i /></span>
            </div>
          </template>
          <!-- 流式尚未产出第一行（或回退非流式）时的保底占位，不让用户干等 -->
          <div v-else class="stream-line current">正在处理，请稍候<span class="dots"><i /><i /><i /></span></div>
        </div>
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
.prov-tag {
  margin-left: 8px;
  vertical-align: middle;
}
.stream-proc {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 2px 0 8px;
  padding: 8px 10px;
  background: #f4f4f5;
  border-radius: 8px;
  font-size: 12px;
}
.stream-line {
  color: #c0c4cc; /* 已完成的状态行：置灰 */
  line-height: 1.6;
  animation: line-in 0.25s ease-out; /* 新行淡入上移 */
}
@keyframes line-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.stream-line.current {
  color: #409eff;
  font-weight: bold;
}
.dots i {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-left: 3px;
  border-radius: 50%;
  background: #409eff;
  animation: dot-bounce 0.9s infinite ease-in-out;
}
.dots i:nth-child(2) {
  animation-delay: 0.15s;
}
.dots i:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes dot-bounce {
  0%, 80%, 100% {
    transform: scale(0.4);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
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
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.chip {
  margin-left: 0 !important;
}
.refs {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
.ref-tag {
  margin: 2px 4px 0 0;
}
.ref-link {
  color: #409eff;
  font-size: 12px;
  margin-right: 8px;
  text-decoration: none;
}
.input-bar {
  display: flex;
  gap: 8px;
  padding-top: 8px;
}
</style>

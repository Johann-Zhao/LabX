<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentChatStream, askQuestion, fetchMaterial, fetchRecords } from '../api'
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

// 常用提问：空状态欢迎区与右栏共用，点击即发送
const SUGGESTIONS = ['我想做自动浇花装置', '我的电机不转', '这块板子能做什么', 'Arduino 还有吗']

// 右栏"在借件数"：null = 未取到（静默降级，该行不显示）
const borrowingCount = ref(null)

const PROVENANCE_META = {
  local_kb: { text: '本地知识库', type: 'success' },
  web: { text: '网络检索', type: 'primary' },
  model: { text: '通用经验', type: 'info' },
  offline: { text: '离线兜底', type: 'warning' },
}

// 右栏数据：借用记录接口失败时静默降级，不影响对话主流程
async function loadBorrowing() {
  try {
    const res = await fetchRecords(currentUser.id)
    if (res.code === 0) {
      borrowingCount.value = res.data.filter((r) => r.status === 'active' || r.status === 'overdue').length
    }
  } catch {
    /* 静默降级：不报错不挡主流程 */
  }
}

// 顶栏切换账号后，右栏"在借件数"跟着换
watch(() => currentUser.id, loadBorrowing)

onMounted(async () => {
  loadBorrowing()
  if (materialId) {
    const res = await fetchMaterial(materialId)
    if (res.code === 0) materialName.value = res.data.name
    messages.value.push({
      role: 'assistant',
      text: `你好，我是${materialName.value || '这件物料'}的专属助教。关于它的接线、用法、踩坑，都可以问我。`,
    })
  }
  // 非物料模式：不再预置长欢迎气泡，空状态欢迎区由模板渲染
})

async function send() {
  const question = input.value.trim()
  if (!question || thinking.value) return
  await sendText(question)
}

// 点击澄清选项/常用提问 = 把文本作为下一条消息发送（同一会话）
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
    <!-- 左侧：对话主栏 -->
    <div class="chat-col">
      <el-alert
        v-if="materialId"
        type="success"
        :closable="false"
        class="ctx"
        :title="`正在围绕「${materialName || materialId}」提问，回答只参考这件物料的知识`"
      />

      <div ref="listRef" class="msg-list">
        <!-- 空状态欢迎区：助手名 + 定位语 + 常用提问（点击即发送） -->
        <div v-if="!messages.length" class="welcome">
          <div class="welcome-name">LabX 智能助手</div>
          <p class="welcome-tagline">说个想法，我出方案并可一键预约物料；遇到故障，我帮你一步步排查。</p>
          <div class="chips">
            <el-button
              v-for="q in SUGGESTIONS"
              :key="q"
              size="small"
              round
              class="chip"
              @click="sendText(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>

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
        >
          <!-- 控制台提示符：mono ›，占位文本仍是中文 -->
          <template #prefix>
            <span class="prompt" aria-hidden="true">›</span>
          </template>
        </el-input>
        <!-- 语音输入占位：功能未上线，仅保留入口位置 -->
        <el-button class="mic-btn" size="large" disabled title="语音输入即将上线" aria-label="语音输入即将上线">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 10a7 7 0 0 0 14 0" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
        </el-button>
        <el-button type="primary" size="large" :loading="thinking" @click="send">发送</el-button>
      </div>
    </div>

    <!-- 右侧快捷栏：仅 ≥1024px 显示，数据失败静默降级；容器卡挂仪器角标 -->
    <aside class="side-col">
      <div class="side-card lx-brackets">
        <div class="user-name">{{ currentUser.name }}</div>
        <div class="user-id lx-num">ID {{ currentUser.id }}</div>
        <!-- 在借件数：仪器读数风（大号 mono 数字 + 小号单位标签） -->
        <div v-if="borrowingCount !== null" class="readout">
          <div class="readout-num lx-num">{{ borrowingCount }}</div>
          <div class="readout-label lx-num">当前在借 · 件</div>
        </div>
      </div>

      <div class="side-card lx-brackets">
        <div class="side-title">快捷入口</div>
        <router-link to="/materials" class="side-link">去借物料</router-link>
        <router-link to="/records" class="side-link">我的借用</router-link>
      </div>

      <div class="side-card lx-brackets">
        <div class="side-title">
          <span>常用提问</span>
          <span class="title-tag lx-num">QA {{ SUGGESTIONS.length }}</span>
        </div>
        <div class="side-chips">
          <el-button
            v-for="q in SUGGESTIONS"
            :key="q"
            size="small"
            round
            class="chip"
            @click="sendText(q)"
          >
            {{ q }}
          </el-button>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.ask-page {
  display: flex;
  gap: var(--lx-space-5);
  height: calc(100vh - 170px);
}

/* ---------- 左侧对话主栏 ---------- */
.chat-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.ctx {
  margin-bottom: var(--lx-space-2);
}
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--lx-space-2) var(--lx-space-1);
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}

/* 空状态欢迎区：克制左对齐，不做营销 hero */
.welcome {
  padding: var(--lx-space-6) var(--lx-space-3) var(--lx-space-4);
}
.welcome-name {
  font-size: var(--lx-text-xl);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
.welcome-tagline {
  margin: var(--lx-space-2) 0 var(--lx-space-4);
  font-size: var(--lx-text-base);
  color: var(--lx-text-secondary);
}

/* 消息：入场 150ms 淡入上移 */
.msg {
  display: flex;
  flex-direction: column;
  max-width: 90%;
  animation: msg-in var(--lx-duration-fast) var(--lx-ease-out);
}
@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
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
  padding: var(--lx-space-3) var(--lx-space-4);
  border-radius: var(--lx-radius-md);
  font-size: var(--lx-text-base);
  line-height: var(--lx-leading);
  white-space: pre-wrap;
  word-break: break-word;
}
.user .bubble {
  background: var(--lx-green);
  color: var(--lx-bg-surface);
}
.assistant .bubble {
  background: var(--lx-bg-surface);
  color: var(--lx-text-regular);
  border: 1px solid var(--lx-border-light);
}
.prov-tag {
  margin-left: var(--lx-space-2);
  vertical-align: middle;
}

/* 过程显化区（流式） */
.stream-proc {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-1);
  margin: var(--lx-space-1) 0 var(--lx-space-2);
  padding: var(--lx-space-2) var(--lx-space-3);
  background: var(--lx-bg-subtle);
  border: 1px solid var(--lx-border-lighter);
  border-radius: var(--lx-radius-md);
  font-size: var(--lx-text-xs);
}
.stream-line {
  color: var(--lx-text-placeholder); /* 已完成的状态行：置灰 */
  line-height: var(--lx-leading);
  animation: line-in var(--lx-duration-base) var(--lx-ease-out); /* 新行淡入上移 */
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
  color: var(--lx-green);
  font-weight: var(--lx-font-semibold);
}
/* 加载中跳动圆点：表达"正在执行"这一真实状态 */
.dots i {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-left: var(--lx-space-1);
  border-radius: 50%;
  background: var(--lx-green);
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

/* 多智能体协作过程（折叠面板） */
.steps {
  margin-bottom: var(--lx-space-1);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  cursor: pointer;
  user-select: none;
}
.steps-toggle:hover {
  color: var(--lx-green);
}
.steps-list {
  margin-top: var(--lx-space-1);
  padding: var(--lx-space-2) var(--lx-space-3);
  background: var(--lx-green-light-9);
  border-left: 3px solid var(--lx-green);
  border-radius: var(--lx-radius-sm);
}
.step-item {
  display: flex;
  flex-direction: column;
  padding: var(--lx-space-1) 0;
}
.step-name {
  color: var(--lx-green);
  font-weight: var(--lx-font-semibold);
}
.step-detail {
  color: var(--lx-text-regular);
}

/* 澄清/常用提问 chips：细边框胶囊，hover 染绿 */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--lx-space-2);
  margin-top: var(--lx-space-2);
}
.chip {
  margin-left: 0 !important;
  background: var(--lx-bg-surface);
  border-color: var(--lx-border);
  color: var(--lx-text-regular);
}
.chip:hover {
  background: var(--lx-green-light-9);
  border-color: var(--lx-green-light-3);
  color: var(--lx-green);
}

/* 参考卡片标签 */
.refs {
  margin-top: var(--lx-space-1);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
}
.ref-tag {
  margin: var(--lx-space-1) var(--lx-space-1) 0 0;
}
.ref-link {
  color: var(--lx-green);
  font-size: var(--lx-text-xs);
  margin-right: var(--lx-space-2);
  text-decoration: none;
}
.ref-link:hover {
  text-decoration: underline;
}

/* 输入栏 */
.input-bar {
  display: flex;
  gap: var(--lx-space-2);
  padding-top: var(--lx-space-3);
  border-top: 1px solid var(--lx-border-lighter);
}
/* 控制台提示符 ›：mono 主绿，借用 el-input 的 prefix 槽垂直居中 */
.prompt {
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-green);
}
.mic-btn {
  flex-shrink: 0;
}

/* ---------- 右侧快捷栏：<1024px 收起，保持单栏流式 ---------- */
.side-col {
  display: none;
}
@media (min-width: 1024px) {
  .chat-col {
    max-width: 760px;
  }
  .side-col {
    display: flex;
    flex-direction: column;
    gap: var(--lx-space-4);
    width: 280px;
    flex-shrink: 0;
  }
}
.side-card {
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  padding: var(--lx-space-4);
}
.side-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: var(--lx-text-xs);
  font-weight: var(--lx-font-medium);
  color: var(--lx-text-secondary);
  margin-bottom: var(--lx-space-3);
}
/* mono 功能标签：真实计数（Linear 的 FIG/ENG 式标注），不贴假数字 */
.title-tag {
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}
.user-name {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
.user-id {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  margin-top: var(--lx-space-1);
}
/* 在借件数读数：细发线之上，大号 mono 数字 + 小号 mono 单位标签 */
.readout {
  margin-top: var(--lx-space-3);
  padding-top: var(--lx-space-3);
  border-top: 1px solid var(--lx-border-lighter);
}
.readout-num {
  font-size: var(--lx-text-3xl);
  font-weight: var(--lx-font-semibold);
  line-height: var(--lx-leading-tight);
  color: var(--lx-text-primary);
}
.readout-label {
  margin-top: var(--lx-space-1);
  font-size: var(--lx-text-xs);
  letter-spacing: 0.08em;
  color: var(--lx-text-secondary);
}
.side-link {
  display: block;
  padding: var(--lx-space-2) var(--lx-space-3);
  border-radius: var(--lx-radius-base);
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
  text-decoration: none;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.side-link:hover {
  background: var(--lx-bg-hover);
  color: var(--lx-green);
}
.side-chips {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--lx-space-2);
}
</style>

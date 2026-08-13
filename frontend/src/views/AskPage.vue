<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentChatStream, askQuestion, fetchMaterial, fetchMaterials, fetchRecords } from '../api'
import { currentUser } from '../store'
import BomCard from './BomCard.vue'
import MaterialImage from '../components/MaterialImage.vue'

const route = useRoute()
const router = useRouter()
const materialId = route.query.material_id || null // 从物料详情页进入时带上（数字分身对话窗）
const materialName = ref('')

// 会话 ID：页面生命周期内不变，用于后端挂起/恢复澄清状态（见 docs/agent-workflow.md）
const convId = `conv-${Date.now()}`
const convIdShort = convId.slice(-6) // 控制台头部只显示尾号，全 ID 无意义

// { role, text, refs, steps, provenance, clarify: {options}, bom }
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const listRef = ref(null)
const expandedSteps = ref({})

// 过程显化区（流式）：等待 final 期间逐行显示真实执行状态，最后一行带跳动圆点
const streamLines = ref([])
const streamActive = ref(false)

// 常用提问：空状态欢迎区指令行，点击即发送
const SUGGESTIONS = ['我想做自动浇花装置', '我的电机不转', '这块板子能做什么', 'Arduino 还有吗']

// 能力矩阵（左轨）：四大机制 → 点击即把对应演示提问送进对话（四幕剧本的入口）
const CAPABILITIES = [
  { code: 'C1', name: '借用即学习', desc: '借后推送关键知识卡片，上手零门槛', prompt: 'Arduino 还有吗' },
  { code: 'C2', name: '愿望到方案', desc: '一句想法转 BOM 清单，可一键预约', prompt: '我想做自动浇花装置' },
  { code: 'C3', name: '排障问答', desc: '物料数字分身随问随答，五步排障', prompt: '我的电机不转' },
  { code: 'C4', name: '经验闭环', desc: '归还心得沉淀为可检索的社区经验', prompt: '这块板子能做什么' },
]

// 快捷功能（右轨）：mono 序号 + 路由链接
const QUICK_LINKS = [
  { idx: '01', to: '/materials', label: '去借物料' },
  { idx: '02', to: '/records', label: '我的借用' },
  { idx: '03', to: '/admin', label: '管理台' },
]

// 右轨"在借件数"：null = 未取到（静默降级，该行不显示）
const borrowingCount = ref(null)

// 右轨物料精选 + 左轨系统状态：真实接口数据，失败静默降级（对应行显示 —）
const materials = ref([])
// 精选 = 在库优先排序 + 轮换窗口（"换一批"按种子滚动，不是无脑截前 4）
const showcaseSeed = ref(0)
const showcase = computed(() => {
  const ranked = [...materials.value].sort(
    (a, b) => (b.available_quantity > 0 ? 1 : 0) - (a.available_quantity > 0 ? 1 : 0)
  )
  const n = ranked.length
  if (n <= 4) return ranked
  const start = showcaseSeed.value % n
  return Array.from({ length: 4 }, (_, i) => ranked[(start + i) % n])
})
function rotateShowcase() {
  showcaseSeed.value += 1
}
const statsTotal = computed(() => (materials.value.length ? materials.value.length : null))
const statsAvail = computed(() =>
  materials.value.length ? materials.value.reduce((s, m) => s + (m.available_quantity || 0), 0) : null
)

// 控制台时钟：秒级跳动的遥测时间（mono 等宽数字不抖动）
const now = ref(new Date())
let clockTimer = null
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false }))

const PROVENANCE_META = {
  local_kb: { text: '本地知识库', cls: 'local' },
  web: { text: '网络检索', cls: 'web' },
  model: { text: '通用经验', cls: 'model' },
  offline: { text: '离线兜底', cls: 'offline' },
}

// 右轨数据：借用记录接口失败时静默降级，不影响对话主流程
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

async function loadMaterials() {
  try {
    const res = await fetchMaterials()
    if (res.code === 0) materials.value = res.data
  } catch {
    /* 静默降级 */
  }
}

// 顶栏切换账号后，右轨"在借件数"跟着换
watch(() => currentUser.id, loadBorrowing)

onMounted(async () => {
  clockTimer = setInterval(() => (now.value = new Date()), 1000)
  loadBorrowing()
  loadMaterials()
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

onUnmounted(() => clearInterval(clockTimer))

async function send() {
  const question = input.value.trim()
  if (!question || thinking.value) return
  await sendText(question)
}

// 点击澄清选项/常用提问/能力矩阵 = 把文本作为下一条消息发送（同一会话）
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
  <!-- 控制台三栏：左能力矩阵 / 中对话 / 右物料+快捷；窄屏塌成单列，侧轨沉到对话下方 -->
  <div class="deck">
    <!-- 左轨：能力矩阵 + 系统状态（≥1280px 在侧，<1024px 沉底） -->
    <aside class="rail rail-left">
      <section class="rail-sec">
        <div class="sec-head">
          <span>能力矩阵</span>
          <span class="sec-tag lx-num">CAP {{ CAPABILITIES.length }}</span>
        </div>
        <button v-for="c in CAPABILITIES" :key="c.code" type="button" class="cap-row" @click="sendText(c.prompt)">
          <span class="cap-code lx-num">{{ c.code }}</span>
          <span class="cap-body">
            <span class="cap-name">{{ c.name }}</span>
            <span class="cap-desc">{{ c.desc }}</span>
          </span>
          <span class="row-arrow" aria-hidden="true">›</span>
        </button>
      </section>

      <section class="rail-sec">
        <div class="sec-head">
          <span>系统状态</span>
          <span class="sec-tag lx-num">SYS</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">物料登记</span>
          <span class="stat-val lx-num">{{ statsTotal ?? '—' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">当前可借</span>
          <span class="stat-val lx-num">{{ statsAvail ?? '—' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">会话</span>
          <span class="stat-val lx-num">{{ convIdShort }}</span>
        </div>
      </section>
    </aside>

    <!-- 中央：对话控制台 -->
    <main class="console">
      <!-- 控制台头：在线 LED + mono 状态行 + 遥测时钟 -->
      <div class="console-head">
        <span class="led" aria-hidden="true"></span>
        <span class="head-title lx-num">LABX AGENT</span>
        <span class="head-status lx-num">ONLINE</span>
        <span class="head-clock lx-num">{{ clock }}</span>
      </div>

      <el-alert
        v-if="materialId"
        type="success"
        :closable="false"
        class="ctx"
        :title="`正在围绕「${materialName || materialId}」提问，回答只参考这件物料的知识`"
      />

      <div ref="listRef" class="msg-list">
        <!-- 空状态欢迎区：雷达徽标 + 定位语 + 指令行（点击即发送） -->
        <div v-if="!messages.length" class="welcome">
          <div class="radar" aria-hidden="true">
            <span class="radar-ring r1"></span>
            <span class="radar-ring r2"></span>
            <span class="radar-sweep"></span>
            <span class="radar-dot"></span>
          </div>
          <div class="welcome-kicker lx-num">LABX · EXPERIENTIAL AGENT</div>
          <div class="welcome-name">说个想法，剩下的交给我</div>
          <p class="welcome-tagline">出方案并可一键预约物料；遇到故障，一步步带你排查。</p>
          <div class="cmd-list">
            <button
              v-for="(q, i) in SUGGESTIONS"
              :key="q"
              type="button"
              class="cmd-row"
              @click="sendText(q)"
            >
              <span class="cmd-idx lx-num">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="cmd-text">{{ q }}</span>
              <span class="row-arrow" aria-hidden="true">›</span>
            </button>
          </div>
        </div>

        <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
          <!-- 智能体协作过程（排障演示的高潮镜头） -->
          <div v-if="m.steps?.length" class="steps" @click="expandedSteps[i] = !expandedSteps[i]">
            <span class="steps-toggle lx-num">
              {{ expandedSteps[i] ? '▾' : '▸' }} 多智能体协作过程（{{ m.steps.length }} 步）
            </span>
            <div v-show="expandedSteps[i]" class="steps-list">
              <div v-for="(s, j) in m.steps" :key="j" class="step-item">
                <span class="step-name lx-num">{{ String(j + 1).padStart(2, '0') }} · {{ s.step }}</span>
                <span class="step-detail">{{ s.detail }}</span>
              </div>
            </div>
          </div>

          <div class="bubble">
            {{ m.text }}
            <span
              v-if="m.provenance && PROVENANCE_META[m.provenance]"
              :class="['prov', 'lx-num', PROVENANCE_META[m.provenance].cls]"
            >
              <span class="prov-dot" aria-hidden="true"></span>{{ PROVENANCE_META[m.provenance].text }}
            </span>
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
              <el-tag
            v-if="r.card_id"
            size="small"
            class="ref-tag"
            role="link"
            tabindex="0"
            @click="router.push(`/cards/${r.card_id}`)"
            @keyup.enter="router.push(`/cards/${r.card_id}`)"
          >
            {{ r.title }}
          </el-tag>
              <a v-else-if="r.url" :href="r.url" target="_blank" rel="noopener" class="ref-link">{{ r.title }} ↗</a>
            </template>
          </div>
        </div>

        <!-- 过程显化区（流式）：终端日志风，真实执行状态逐行显示，当前行带跳动圆点 -->
        <div v-if="thinking" class="msg assistant">
          <div class="stream-proc">
            <template v-if="streamLines.length">
              <div
                v-for="(line, i) in streamLines"
                :key="i"
                :class="['stream-line', 'lx-num', { current: streamActive && i === streamLines.length - 1 }]"
              >
                <span class="stream-prefix" aria-hidden="true">›</span>{{ line }}
                <span v-if="streamActive && i === streamLines.length - 1" class="dots"><i /><i /><i /></span>
              </div>
            </template>
            <!-- 流式尚未产出第一行（或回退非流式）时的保底占位，不让用户干等 -->
            <div v-else class="stream-line lx-num current">
              <span class="stream-prefix" aria-hidden="true">›</span>正在处理，请稍候<span class="dots"><i /><i /><i /></span>
            </div>
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
    </main>

    <!-- 右轨：用户读数 + 物料精选 + 快捷功能（≥1024px 在侧，窄屏沉底） -->
    <aside class="rail rail-right">
      <section class="rail-sec">
        <div class="sec-head">
          <span>当前用户</span>
          <span class="sec-tag lx-num">USER</span>
        </div>
        <div class="user-name">{{ currentUser.name }}</div>
        <div class="user-id lx-num">ID {{ currentUser.id }}</div>
        <!-- 在借件数：仪器读数风（大号 mono 数字 + 小号单位标签） -->
        <div v-if="borrowingCount !== null" class="readout">
          <div class="readout-num lx-num">{{ borrowingCount }}</div>
          <div class="readout-label lx-num">当前在借 · 件</div>
        </div>
      </section>

      <section class="rail-sec">
        <div class="sec-head">
          <span>物料精选</span>
          <span class="sec-actions">
            <span class="sec-tag lx-num">MAT {{ showcase.length }}</span>
            <button
              v-if="materials.length > 4"
              type="button"
              class="rotate-btn lx-num"
              @click="rotateShowcase"
            >
              换一批
            </button>
          </span>
        </div>
        <router-link v-for="m in showcase" :key="m.material_id" :to="`/materials/${m.material_id}`" class="mat-row">
          <MaterialImage :material-id="m.material_id" :name="m.name" class="mat-thumb" />
          <span class="mat-body">
            <span class="mat-name">{{ m.name }}</span>
            <span class="mat-meta lx-num">{{ m.material_id }}</span>
          </span>
          <span :class="['mat-stock', 'lx-num', { empty: m.available_quantity === 0 }]">
            <span class="stock-dot" aria-hidden="true"></span>
            {{ m.available_quantity === 0 ? '借空' : `×${m.available_quantity}` }}
          </span>
        </router-link>
        <div v-if="!showcase.length" class="mat-empty lx-num">NO DATA</div>
      </section>

      <section class="rail-sec">
        <div class="sec-head">
          <span>快捷功能</span>
          <span class="sec-tag lx-num">NAV</span>
        </div>
        <router-link v-for="l in QUICK_LINKS" :key="l.to" :to="l.to" class="qlink">
          <span class="q-idx lx-num">{{ l.idx }}</span>
          <span class="q-label">{{ l.label }}</span>
          <span class="row-arrow" aria-hidden="true">›</span>
        </router-link>
      </section>
    </aside>
  </div>
</template>

<style scoped>
/* ==========================================================================
   布局：控制台三栏（deck）
   ≥1280px：左轨 248px + 中对话 + 右轨 288px
   1024-1279px：左轨收窄到 200px 保留能力矩阵入口 + 中对话 + 右轨 288px
   <1024px：单列，对话在上，两条侧轨沉到下方
   ========================================================================== */
.deck {
  display: flex;
  gap: var(--lx-space-5);
  height: calc(100dvh - 170px);
  min-height: 520px; /* 小屏笔记本/浏览器栏变化时不被裁死 */
}

/* ---------- 中央对话控制台 ---------- */
.console {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  overflow: hidden;
}

/* 控制台头：发线分隔，mono 状态行 */
.console-head {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  padding: var(--lx-space-2) var(--lx-space-4);
  border-bottom: 1px solid var(--lx-border-lighter);
  flex-shrink: 0;
}
/* 在线 LED：主绿圆点 + 呼吸光晕（状态表达，非装饰） */
.led {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--lx-green);
  box-shadow: 0 0 0 0 var(--lx-green-glow);
  animation: led-pulse 1.6s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes led-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 var(--lx-green-glow);
  }
  50% {
    box-shadow: 0 0 0 5px transparent;
  }
}
.head-title {
  font-size: var(--lx-text-xs);
  font-weight: var(--lx-font-semibold);
  letter-spacing: 0.12em;
  color: var(--lx-text-primary);
}
.head-status {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-green);
}
.head-clock {
  margin-left: auto;
  font-size: var(--lx-text-xs);
  letter-spacing: 0.06em;
  color: var(--lx-text-placeholder);
}
.ctx {
  margin: var(--lx-space-2) var(--lx-space-3) 0;
  flex-shrink: 0;
}

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--lx-space-3) var(--lx-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
  /* 细滚动条（6px）：贴边不抢戏 */
  scrollbar-width: thin;
  scrollbar-color: var(--lx-border-strong) transparent;
}
.msg-list::-webkit-scrollbar {
  width: 6px;
}
.msg-list::-webkit-scrollbar-thumb {
  background: var(--lx-border-strong);
  border-radius: var(--lx-radius-pill);
}
.msg-list::-webkit-scrollbar-track {
  background: transparent;
}

/* ---------- 空状态欢迎区 ---------- */
.welcome {
  margin: auto 0; /* 消息少时垂直居中，控制台感 */
  padding: var(--lx-space-5) var(--lx-space-2) var(--lx-space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
/* 雷达徽标：双环 + 旋转扫掠 + 中心呼吸点，纯 CSS 画，无图片依赖 */
.radar {
  position: relative;
  width: 72px;
  height: 72px;
  margin-bottom: var(--lx-space-4);
}
.radar-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid var(--lx-green-light-7);
}
.radar-ring.r1 {
  inset: 0;
}
.radar-ring.r2 {
  inset: 18px;
  border-color: var(--lx-green-light-8);
}
/* 扫掠：锥形渐变转一圈 4.2s，尾迹衰减 */
.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(from 0deg, var(--lx-green-glow), var(--lx-green-glow-soft) 90deg, transparent 120deg);
  animation: radar-sweep 4.2s linear infinite;
}
@keyframes radar-sweep {
  to {
    transform: rotate(360deg);
  }
}
.radar-dot {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 8px;
  height: 8px;
  margin: -4px 0 0 -4px;
  border-radius: 50%;
  background: var(--lx-green);
  box-shadow: 0 0 0 0 var(--lx-green-glow);
  animation: led-pulse 1.6s ease-in-out infinite;
}
.welcome-kicker {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.18em;
  color: var(--lx-green);
  margin-bottom: var(--lx-space-2);
}
.welcome-name {
  font-size: var(--lx-text-2xl);
  font-weight: var(--lx-font-bold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
.welcome-tagline {
  margin: var(--lx-space-2) 0 var(--lx-space-5);
  font-size: var(--lx-text-base);
  color: var(--lx-text-secondary);
}

/* 指令行：mono 序号 + 文本 + ›，发线分隔，hover 整行染浅绿（命令面板语言） */
.cmd-list {
  width: 100%;
  max-width: 420px;
  border-top: 1px solid var(--lx-border-light);
}
.cmd-row {
  display: flex;
  align-items: center;
  gap: var(--lx-space-3);
  width: 100%;
  padding: var(--lx-space-3) var(--lx-space-2);
  border: none;
  border-bottom: 1px solid var(--lx-border-light);
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.cmd-idx {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
  transition: color var(--lx-duration-fast) var(--lx-ease-out);
}
.cmd-text {
  flex: 1;
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
}
.cmd-row:hover {
  background: var(--lx-green-light-9);
}
.cmd-row:hover .cmd-idx,
.cmd-row:hover .row-arrow {
  color: var(--lx-green);
}

/* 行尾 › 箭头：cap/cmd/qlink 共用 */
.row-arrow {
  font-family: var(--lx-font-mono);
  color: var(--lx-text-placeholder);
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    transform var(--lx-duration-fast) var(--lx-ease-out);
}
.cmd-row:hover .row-arrow,
.cap-row:hover .row-arrow,
.qlink:hover .row-arrow {
  transform: translateX(2px);
}

/* 键盘可达性：指令行/能力行/快捷行 focus 可见描边 */
.cmd-row:focus-visible,
.cap-row:focus-visible,
.qlink:focus-visible,
.mat-row:focus-visible {
  outline: 2px solid var(--lx-green);
  outline-offset: -2px;
}

/* ---------- 消息 ---------- */
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
  background: var(--lx-bg-subtle);
  color: var(--lx-text-regular);
}

/* provenance：mono 小标 + 状态点（替代 el-tag 胶囊，更贴控制台语言） */
.prov {
  display: inline-flex;
  align-items: center;
  gap: var(--lx-space-1);
  margin-left: var(--lx-space-2);
  font-size: var(--lx-text-xs);
  letter-spacing: 0.04em;
  vertical-align: middle;
}
.prov-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.prov.local {
  color: var(--lx-green);
}
.prov.local .prov-dot {
  background: var(--lx-green);
}
.prov.web,
.prov.model {
  color: var(--lx-info);
}
.prov.web .prov-dot,
.prov.model .prov-dot {
  background: var(--lx-info);
}
.prov.offline {
  color: var(--lx-warning);
}
.prov.offline .prov-dot {
  background: var(--lx-warning);
}

/* ---------- 过程显化区（流式）：终端日志风 ---------- */
.stream-proc {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-1);
  margin: var(--lx-space-1) 0 var(--lx-space-2);
  padding: var(--lx-space-2) var(--lx-space-3);
  background: var(--lx-bg-subtle);
  border-left: 2px solid var(--lx-green-light-7);
  border-radius: 0 var(--lx-radius-sm) var(--lx-radius-sm) 0;
  font-size: var(--lx-text-xs);
}
.stream-line {
  color: var(--lx-text-placeholder); /* 已完成的状态行：置灰 */
  line-height: var(--lx-leading);
  animation: line-in var(--lx-duration-base) var(--lx-ease-out);
}
.stream-prefix {
  margin-right: var(--lx-space-2);
  color: var(--lx-green-light-5);
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

/* ---------- 多智能体协作过程（折叠面板） ---------- */
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
  border-left: 2px solid var(--lx-green);
  border-radius: 0 var(--lx-radius-sm) var(--lx-radius-sm) 0;
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

/* 澄清 chips：细边框胶囊，hover 染绿 */
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
  cursor: pointer;
  transition: border-color var(--lx-duration-fast) var(--lx-ease-out);
}
.ref-tag:hover {
  border-color: var(--lx-green-light-3);
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

/* ---------- 输入栏 ---------- */
.input-bar {
  display: flex;
  gap: var(--lx-space-2);
  padding: var(--lx-space-3) var(--lx-space-4);
  border-top: 1px solid var(--lx-border-lighter);
  flex-shrink: 0;
}
/* 控制台提示符 ›：mono 主绿，借用 el-input 的 prefix 槽垂直居中 */
.prompt {
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-green);
}
/* 聚焦辉光：输入框获得焦点时一圈主绿微光（状态表达） */
.input-bar :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px var(--lx-green) inset,
    0 0 0 4px var(--lx-green-glow-soft);
}
.mic-btn {
  flex-shrink: 0;
}

/* ---------- 侧轨共用 ---------- */
.rail {
  display: none;
  flex-direction: column;
  gap: var(--lx-space-4);
  flex-shrink: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--lx-border-strong) transparent;
}
.rail-sec {
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  padding: var(--lx-space-3) var(--lx-space-3);
}
.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: var(--lx-text-xs);
  font-weight: var(--lx-font-medium);
  color: var(--lx-text-secondary);
  margin-bottom: var(--lx-space-2);
}
/* mono 功能标签：细边框小芯片，与区块标题明确区分（防 CAP/SYS 与标题视觉混淆） */
.sec-tag {
  letter-spacing: 0.1em;
  color: var(--lx-text-secondary);
  padding: 0 var(--lx-space-1);
  border: 1px solid var(--lx-border-light);
  border-radius: 3px;
  line-height: 1.5;
}
.sec-actions {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
}
/* 换一批：文字级操作按钮，hover 染主绿 */
.rotate-btn {
  padding: 0;
  border: none;
  background: none;
  font-size: var(--lx-text-xs);
  letter-spacing: 0.06em;
  color: var(--lx-text-secondary);
  cursor: pointer;
  transition: color var(--lx-duration-fast) var(--lx-ease-out);
}
.rotate-btn:hover {
  color: var(--lx-green);
}

/* 能力矩阵行：无容器嵌套，发线分隔 */
.cap-row {
  display: flex;
  align-items: center;
  gap: var(--lx-space-3);
  width: 100%;
  padding: var(--lx-space-3) var(--lx-space-1);
  border: none;
  border-bottom: 1px solid var(--lx-border-lighter);
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.cap-row:last-of-type {
  border-bottom: none;
}
.cap-code {
  font-size: var(--lx-text-xs);
  font-weight: var(--lx-font-semibold);
  letter-spacing: 0.08em;
  color: var(--lx-green);
  flex-shrink: 0;
}
.cap-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.cap-name {
  font-size: var(--lx-text-base);
  font-weight: var(--lx-font-medium);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
.cap-desc {
  margin-top: 2px;
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  line-height: var(--lx-leading-tight);
}
.cap-row:hover {
  background: var(--lx-green-light-9);
}

/* 系统状态行：label 左、mono 读数右 */
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--lx-space-2) var(--lx-space-1);
  border-bottom: 1px solid var(--lx-border-lighter);
}
.stat-row:last-child {
  border-bottom: none;
}
.stat-label {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
}
.stat-val {
  font-size: var(--lx-text-sm);
  font-weight: var(--lx-font-medium);
  color: var(--lx-text-primary);
}

/* 用户读数 */
.user-name {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
  padding: 0 var(--lx-space-1);
}
.user-id {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  margin-top: var(--lx-space-1);
  padding: 0 var(--lx-space-1);
}
.readout {
  margin: var(--lx-space-3) var(--lx-space-1) 0;
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

/* 物料精选行：缩略图 + 名称/编号 + 库存状态点 */
.mat-row {
  display: flex;
  align-items: center;
  gap: var(--lx-space-3);
  padding: var(--lx-space-2) var(--lx-space-1);
  border-bottom: 1px solid var(--lx-border-lighter);
  text-decoration: none;
  transition: background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.mat-row:last-of-type {
  border-bottom: none;
}
.mat-row:hover {
  background: var(--lx-bg-hover);
}
.mat-thumb {
  width: 44px;
  height: 44px;
  border-radius: var(--lx-radius-base);
  border: 1px solid var(--lx-border-light);
  flex-shrink: 0;
  --mimg-fs: var(--lx-text-md);
}
.mat-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.mat-name {
  font-size: var(--lx-text-sm);
  font-weight: var(--lx-font-medium);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mat-meta {
  margin-top: 2px;
  font-size: var(--lx-text-xs);
  color: var(--lx-text-placeholder);
}
.mat-stock {
  display: inline-flex;
  align-items: center;
  gap: var(--lx-space-1);
  font-size: var(--lx-text-xs);
  color: var(--lx-green);
  flex-shrink: 0;
}
.stock-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lx-green);
  box-shadow: 0 0 0 0 var(--lx-green-glow);
  animation: led-pulse 1.6s ease-in-out infinite;
}
.mat-stock.empty {
  color: var(--lx-text-placeholder);
}
.mat-stock.empty .stock-dot {
  background: var(--lx-text-disabled);
  animation: none;
  box-shadow: none;
}
.mat-empty {
  padding: var(--lx-space-3) var(--lx-space-1);
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}

/* 快捷功能行 */
.qlink {
  display: flex;
  align-items: center;
  gap: var(--lx-space-3);
  padding: var(--lx-space-2) var(--lx-space-1);
  border-bottom: 1px solid var(--lx-border-lighter);
  text-decoration: none;
  transition: background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.qlink:last-child {
  border-bottom: none;
}
.qlink:hover {
  background: var(--lx-green-light-9);
}
.q-idx {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}
.qlink:hover .q-idx {
  color: var(--lx-green);
}
.q-label {
  flex: 1;
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
}

/* ---------- 响应式 ---------- */
@media (min-width: 1024px) {
  .rail-right {
    display: flex;
    width: 288px;
  }
  .rail-left {
    display: flex;
    width: 200px; /* 1024-1279 档：左轨收窄但保留能力矩阵入口 */
  }
}
@media (min-width: 1280px) {
  .rail-left {
    width: 248px;
  }
}
@media (max-width: 1023px) {
  .deck {
    flex-direction: column;
    height: auto;
  }
  .console {
    order: -1;
    height: calc(100dvh - 170px);
    min-height: 420px;
    flex: none;
  }
  .rail {
    display: flex;
    width: 100%;
    overflow: visible;
  }
}
</style>

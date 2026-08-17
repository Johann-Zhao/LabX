<script setup>
// ==========================================================================
// IntroOverlay —— 单屏开屏动画（第八轮）
// 1:1 仿 deepseek.com/harness 首屏的动画语言：
//   - 深色暗场 + 规则 90px 点阵 canvas（鼠标斥力、静止自动停帧）
//   - Seedream 5.0 Pro 生成的视觉图 screen 混合 + 缓慢呼吸 + 轻微鼠标视差
//   - 左文右终端，内容分块 opacity + translateY + blur 依次入场
//   - 终端卡片：tab 切换 + mono 绿色 $ 前缀 + 复制按钮
//
// 交互规则沿用队长拍板：
// - 仅首次访问播放：localStorage 键 labx_intro_seen=1 标记已看；
//   /admin 不渲染本组件（App.vue 控制）；/login 允许播放（首访流程：动画 → 登录页）。
// - 右上角"跳过"、Esc、主按钮均可结束；结束淡出 400ms 后移除 DOM。
// - prefers-reduced-motion：不起 canvas、不建循环动画，所有内容静态直接可见。
// - 视觉图加载失败 @error 隐藏图片，只留暗场光晕 + 点阵（优雅降级）。
// - 组件 visible=false 只收起模板，本体不卸载：清理必须集中在 cleanupAll()。
// - 开屏豁免（docs/design/labx-ui.md 第 8 节）：本页允许循环氛围动画与
//   叙事假终端；本次为对齐 harness 固定深色开屏（应用主题不受影响）。
// ==========================================================================
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { currentUser } from '../store'

const router = useRouter()

// ---------- 是否播放 ----------
const visible = ref(false)
try {
  visible.value = localStorage.getItem('labx_intro_seen') !== '1'
} catch {
  visible.value = false // 隐私模式等异常：不挡路，直接进主界面
}

// 系统开"减少动态效果"：不建 canvas、不起循环动画
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
// 精细指针设备才做鼠标交互（触屏只画一帧静态点阵，不监听移动）
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches

// ---------- 终端卡片数据 ----------
const TERM_TABS = [
  {
    id: 'quick',
    label: '快速开始',
    title: 'labx@console',
    lines: [
      { prompt: true, text: 'cd LabX && npm run dev' },
      { prompt: true, text: 'uvicorn main:app' },
      { prompt: true, text: '登录学生号 2024001 / 123456' },
      { ok: true, text: '✓ 前端 5173 · 后端 8000 在线' },
    ],
  },
  {
    id: 'powers',
    label: '能力清单',
    title: 'labx@console',
    lines: [
      { prompt: true, text: '借物料 → 自动推知识卡' },
      { prompt: true, text: '说现象 → 五步排障 + 经验溯源' },
      { prompt: true, text: '说愿望 → BOM 清单 + 在库预约' },
      { ok: true, text: '✓ 15 件物料 · 33 张卡片 · 闭环已通' },
    ],
  },
]
const activeTermId = ref('quick')
const activeTerm = computed(() => TERM_TABS.find((t) => t.id === activeTermId.value) || TERM_TABS[0])
const copied = ref(false)
let copyTimer = 0

// 复制当前终端命令；clipboard 失败时降级为隐藏 textarea + execCommand
async function copyTerminal() {
  const text = activeTerm.value.lines
    .map((l) => (l.prompt ? `$ ${l.text}` : l.text))
    .join('\n')
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
    } else {
      throw new Error('clipboard unavailable')
    }
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copied.value = true
  clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copied.value = false }, 1600)
}

// ---------- 收尾 ----------
const leaving = ref(false)
let leaveTimer = 0

// 统一清理：停 canvas、移监听、恢复 body 滚动。finish() 与 onBeforeUnmount 都调用，幂等。
function cleanupAll() {
  stopCanvas()
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('pointermove', onPointerMove)
  document.body.style.overflow = ''
}

// 标记已看 + 清理 + 淡出后收起；未登录收尾落登录页（首访流程：动画 → 登录）
function finish() {
  if (leaving.value) return // 防 Esc/按钮连点重复触发
  try { localStorage.setItem('labx_intro_seen', '1') } catch { /* 写不进就算了 */ }
  cleanupAll()
  leaving.value = true
  if (!currentUser.role) router.push('/login') // 已登录则原地不动
  leaveTimer = setTimeout(() => { visible.value = false }, 400)
}

// 副按钮：切到"能力清单" tab（真实交互，非摆设）
function showPowers() {
  activeTermId.value = 'powers'
}

// ---------- 90px 规则点阵 canvas（仿 harness：30fps、鼠标 140px 斥力、静止停帧） ----------
const overlayRef = ref(null)
const canvasRef = ref(null)
let gridCtx = null
let rafId = 0
let dots = []
let cols = 0
let rows = 0
let canvasW = 0
let canvasH = 0
let lastFrame = 0
let settled = false
let mouseX = NaN
let mouseY = NaN
let gridRgb = '244, 244, 245' // 兜底：深色主题近白 #f4f4f5
const SPACING = 90
const TOUCH_RADIUS = 140
const FRAME_MS = 1000 / 30

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16)
  if (Number.isNaN(n)) return null
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
}

function readGridColor() {
  const canvas = canvasRef.value
  if (!canvas) return
  const styles = getComputedStyle(canvas)
  const primary = styles.getPropertyValue('--lx-text-primary').trim()
  if (primary.startsWith('#')) {
    const rgb = hexToRgb(primary)
    if (rgb) gridRgb = rgb
  }
}

function buildDots() {
  const canvas = canvasRef.value
  if (!canvas) return
  canvasW = canvas.clientWidth || window.innerWidth
  canvasH = canvas.clientHeight || window.innerHeight
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = Math.round(canvasW * dpr)
  canvas.height = Math.round(canvasH * dpr)
  if (gridCtx) gridCtx.setTransform(dpr, 0, 0, dpr, 0, 0)

  // 90px 方格均匀铺满，整体居中（与 harness 相同的布局算法）
  cols = Math.ceil(canvasW / SPACING) + 1
  rows = Math.ceil(canvasH / SPACING) + 1
  const offsetX = (canvasW - (cols - 1) * SPACING) / 2
  const offsetY = (canvasH - (rows - 1) * SPACING) / 2
  dots = []
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = offsetX + c * SPACING
      const y = offsetY + r * SPACING
      dots.push({ restX: x, restY: y, x, y, vx: 0, vy: 0 })
    }
  }
}

function drawGridFrame(now) {
  if (reducedMotion || !gridCtx || !canvasRef.value) return
  if (now - lastFrame < FRAME_MS) {
    rafId = requestAnimationFrame(drawGridFrame)
    return
  }
  lastFrame = now - ((now - lastFrame) % FRAME_MS)

  const canvas = canvasRef.value
  if (canvas.clientWidth !== canvasW || canvas.clientHeight !== canvasH) {
    buildDots()
  }

  gridCtx.clearRect(0, 0, canvasW, canvasH)

  // 物理：鼠标 140px 内斥力 + 回位弹簧 + 速度衰减
  let maxSpeed = 0
  for (const p of dots) {
    const dx = p.x - mouseX
    const dy = p.y - mouseY
    const dist = Math.hypot(dx, dy)
    if (dist < TOUCH_RADIUS && dist > 0.1) {
      const force = (1 - dist / TOUCH_RADIUS) * 30
      const ux = dx / dist
      const uy = dy / dist
      p.vx += ux * force * 0.1
      p.vy += uy * force * 0.1
    }
    const springX = p.restX - p.x
    const springY = p.restY - p.y
    p.vx += 0.05 * springX
    p.vy += 0.05 * springY
    p.vx *= 0.85
    p.vy *= 0.85
    p.x += p.vx
    p.y += p.vy
    maxSpeed = Math.max(maxSpeed, Math.abs(p.vx) + Math.abs(p.vy))
  }

  // 相邻点之间画短线段（两端各留 10px，与 harness 相同的断线点阵）
  gridCtx.strokeStyle = `rgba(${gridRgb}, 0.08)`
  gridCtx.lineWidth = 0.5
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols - 1; c++) {
      const a = dots[r * cols + c]
      const b = dots[r * cols + c + 1]
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.hypot(dx, dy)
      if (dist < 20) continue
      const ux = dx / dist
      const uy = dy / dist
      gridCtx.beginPath()
      gridCtx.moveTo(a.x + 10 * ux, a.y + 10 * uy)
      gridCtx.lineTo(b.x - 10 * ux, b.y - 10 * uy)
      gridCtx.stroke()
    }
  }
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows - 1; r++) {
      const a = dots[r * cols + c]
      const b = dots[(r + 1) * cols + c]
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.hypot(dx, dy)
      if (dist < 20) continue
      const ux = dx / dist
      const uy = dy / dist
      gridCtx.beginPath()
      gridCtx.moveTo(a.x + 10 * ux, a.y + 10 * uy)
      gridCtx.lineTo(b.x - 10 * ux, b.y - 10 * uy)
      gridCtx.stroke()
    }
  }

  // 点：基础 1.8px 小方块，鼠标靠近时变大变亮（与 harness 相同）
  gridCtx.fillStyle = `rgba(${gridRgb}, 0.16)`
  for (const p of dots) {
    let half = 1.8
    let alpha = 0.16
    if (!Number.isNaN(mouseX) && !Number.isNaN(mouseY)) {
      const dx = p.x - mouseX
      const dy = p.y - mouseY
      const dist = Math.hypot(dx, dy)
      const glow = Math.max(0, 1 - dist / TOUCH_RADIUS)
      half = 1.8 + 2 * glow
      alpha = 0.16 + 0.4 * glow
    }
    gridCtx.globalAlpha = alpha
    const side = half * 2
    gridCtx.fillRect(p.x - half, p.y - half, side, side)
  }
  gridCtx.globalAlpha = 1

  // 静止（最大速度 < 0.01）就停帧省电；指针移动时再 kick 唤醒
  if (maxSpeed < 0.01) {
    settled = true
    rafId = 0
    return
  }
  rafId = requestAnimationFrame(drawGridFrame)
}

function kickCanvas() {
  if (reducedMotion || !gridCtx) return
  settled = false
  if (!rafId) rafId = requestAnimationFrame(drawGridFrame)
}

function startCanvas() {
  if (reducedMotion) return
  const canvas = canvasRef.value
  if (!canvas) return
  gridCtx = canvas.getContext('2d')
  if (!gridCtx) return
  readGridColor()
  buildDots()
  settled = false
  lastFrame = 0
  rafId = requestAnimationFrame(drawGridFrame)
  window.addEventListener('resize', onResize)
  if (finePointer) window.addEventListener('pointermove', onPointerMove)
}

function stopCanvas() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
}

function onResize() {
  if (!gridCtx) return
  buildDots()
  kickCanvas()
}

// 指针移动：更新点阵斥力中心 + 视觉图轻微视差（只动 transform，不触发布局）
function onPointerMove(e) {
  const canvas = canvasRef.value
  if (canvas) {
    const rect = canvas.getBoundingClientRect()
    mouseX = e.clientX - rect.left
    mouseY = e.clientY - rect.top
    kickCanvas()
  }
  const overlay = overlayRef.value
  if (!overlay || reducedMotion) return
  const rect = overlay.getBoundingClientRect()
  const nx = (e.clientX - rect.left) / Math.max(rect.width, 1) - 0.5
  const ny = (e.clientY - rect.top) / Math.max(rect.height, 1) - 0.5
  overlay.style.setProperty('--intro-mx', `${(-nx * 14).toFixed(1)}px`)
  overlay.style.setProperty('--intro-my', `${(-ny * 10).toFixed(1)}px`)
}

// ---------- 键盘跳过（只留 Esc） ----------
function onKeydown(e) {
  if (e.key === 'Escape') finish()
}

// ---------- 视觉图加载状态（优雅降级） ----------
const heroImgFailed = ref(false)
const heroImgLoaded = ref(false)
function onHeroImgError() { heroImgFailed.value = true }
function onHeroImgLoad() { heroImgLoaded.value = true }

// ---------- 挂载 / 卸载 ----------
onMounted(() => {
  if (!visible.value) return
  document.body.style.overflow = 'hidden' // 单屏开屏：锁住主页面滚动
  window.addEventListener('keydown', onKeydown)
  startCanvas()
})

onBeforeUnmount(() => {
  clearTimeout(leaveTimer)
  clearTimeout(copyTimer)
  cleanupAll()
})
</script>

<template>
  <!-- 固定深色开屏（对齐 harness 首屏暗场；应用主题仍由 <html> 上的 labx_theme 决定） -->
  <div
    v-if="visible"
    ref="overlayRef"
    class="intro-overlay"
    :class="{ 'is-leaving': leaving }"
    data-theme="dark"
  >
    <!-- z0：暗场光晕（软绿径向渐变，慢速漂移） -->
    <div class="intro-aurora" aria-hidden="true"></div>

    <!-- z2：Seedream 5.0 Pro 主视觉，screen 混合压在暗场上 -->
    <div
      class="hero-visual"
      :class="{ 'is-loaded': heroImgLoaded, 'is-failed': heroImgFailed }"
      aria-hidden="true"
    >
      <div class="hero-visual-drift">
        <img
          v-if="!heroImgFailed"
          class="hero-visual-img"
          src="/intro/hero-dark.png"
          alt=""
          @error="onHeroImgError"
          @load="onHeroImgLoad"
        />
      </div>
    </div>

    <!-- z5：规则点阵 canvas（仿 harness 第二层背景） -->
    <canvas ref="canvasRef" class="intro-canvas" aria-hidden="true"></canvas>

    <!-- z30：右上角跳过 -->
    <button type="button" class="skip-btn" @click="finish">跳过</button>

    <!-- z10：左文右终端内容 -->
    <main class="hero">
      <div class="hero-grid">
        <div class="hero-copy">
          <!-- 块 1：eyebrow + 大标题，blur 最深、位移最大 -->
          <div
            class="enter"
            style="--enter-y: 24px; --enter-blur: 10px; animation-duration: 0.9s"
          >
            <p class="hero-eyebrow lx-num">LABX // 高校创新空间</p>
            <h1 class="hero-title">物料有去处<br />知识有回路</h1>
          </div>

          <!-- 块 2：两行说明 -->
          <div
            class="enter enter-desc"
            style="--enter-y: 20px; --enter-blur: 8px; animation-delay: 0.15s"
          >
            <p class="hero-desc">
              借出自动登记去向，借什么就推什么知识卡；归还写下心得，经验留给下一个人。
            </p>
            <p class="hero-desc">
              问答、排障、愿望到方案，全都在同一个控制台里完成。
            </p>
          </div>

          <!-- 块 3：双按钮 -->
          <div
            class="enter enter-actions"
            style="--enter-y: 16px; animation-duration: 0.7s; animation-delay: 0.3s"
          >
            <button type="button" class="btn btn-primary" @click="finish">进入 LabX</button>
            <button type="button" class="btn btn-secondary" @click="showPowers">能力清单</button>
          </div>
        </div>

        <!-- 块 4：终端卡片（右列） -->
        <div
          class="enter enter-term"
          style="--enter-y: 20px; animation-duration: 0.9s; animation-delay: 0.4s"
        >
          <div class="term-card">
            <!-- tab 切换：真实交互，切终端内容 -->
            <div class="term-tabs" role="tablist" aria-label="开屏终端内容">
              <button
                v-for="t in TERM_TABS"
                :key="t.id"
                type="button"
                class="term-tab"
                :class="{ on: activeTermId === t.id }"
                role="tab"
                :aria-selected="activeTermId === t.id"
                @click="activeTermId = t.id"
              >
                {{ t.label }}
              </button>
            </div>

            <div class="term-bar">
              <span class="term-dot term-dot-close" aria-hidden="true"></span>
              <span class="term-dot term-dot-min" aria-hidden="true"></span>
              <span class="term-dot term-dot-max" aria-hidden="true"></span>
              <span class="term-title lx-num">{{ activeTerm.title }}</span>
              <button type="button" class="term-copy" @click="copyTerminal">
                {{ copied ? '已复制' : '复制' }}
              </button>
            </div>

            <div class="term-body">
              <Transition name="term-fade" mode="out-in">
                <pre :key="activeTerm.id" class="term-pre"><template v-for="(line, i) in activeTerm.lines" :key="i"><span :class="{ 'term-ok': line.ok }"><span v-if="line.prompt" class="term-prompt">$</span>{{ line.text }}</span><br v-if="i < activeTerm.lines.length - 1" /></template></pre>
              </Transition>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* 固定深色开屏：根元素挂 data-theme="dark"，所有颜色继续走 --lx-* 深色令牌 */
.intro-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--lx-z-header);
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--lx-bg-page);
  color: var(--lx-text-primary);
  font-family: var(--lx-font-sans);
  transition: opacity var(--lx-duration-slow) var(--lx-ease-standard);
  scrollbar-width: none; /* 开屏短内容：隐藏滚动条，保留小屏可滚 */
}
.intro-overlay::-webkit-scrollbar {
  display: none;
}
.intro-overlay.is-leaving {
  opacity: 0;
  pointer-events: none;
}

/* ---------- z0 暗场光晕 ---------- */
.intro-aurora {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}
.intro-aurora::before,
.intro-aurora::after {
  content: '';
  position: absolute;
  width: 120vw;
  height: 60vh;
  border-radius: 50%;
  filter: blur(60px);
}
.intro-aurora::before {
  left: -30vw;
  top: -18vh;
  background: radial-gradient(closest-side, var(--lx-green-glow-soft), transparent 70%);
  animation: aurora-drift 26s var(--lx-ease-standard) infinite alternate;
}
.intro-aurora::after {
  right: -34vw;
  bottom: -20vh;
  background: radial-gradient(closest-side, var(--lx-green-glow-soft), transparent 70%);
  animation: aurora-drift 34s var(--lx-ease-standard) infinite alternate-reverse;
}
@keyframes aurora-drift {
  from { transform: translate3d(-4vw, 0, 0) scale(1); }
  to { transform: translate3d(4vw, 0, 0) scale(1.08); }
}

/* ---------- z2 Seedream 主视觉 ----------
   screen 混合：图内黑色背景不污染暗场，只有发光主体叠亮；
   入场复刻 harness 背景层：blur(20px) → 0，1.8s ease-out。 */
.hero-visual {
  position: fixed;
  left: 50%;
  top: 50%;
  z-index: 2;
  width: min(800px, 92vw);
  aspect-ratio: 1;
  margin-left: var(--lx-space-7); /* 与 harness 一致：视觉中心略右移，给左文让位 */
  transform: translate(-50%, -50%);
  mix-blend-mode: screen;
  pointer-events: none;
  opacity: 0;
  filter: blur(20px);
  animation: visual-in 1.8s var(--lx-ease-out) 0.1s forwards;
}
@keyframes visual-in {
  to { opacity: 0.85; filter: blur(0); }
}
.hero-visual.is-failed {
  animation: none;
  opacity: 0;
}
.hero-visual-drift {
  width: 100%;
  height: 100%;
  animation: visual-breathe 9s var(--lx-ease-standard) infinite alternate;
}
@keyframes visual-breathe {
  from { transform: scale(1); }
  to { transform: scale(1.045); }
}
.hero-visual-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity var(--lx-duration-slow) var(--lx-ease-out);
  /* --intro-mx/--intro-my 由 pointermove 写入，做轻微视差 */
  transform: translate3d(var(--intro-mx, 0px), var(--intro-my, 0px), 0);
}
.hero-visual.is-loaded .hero-visual-img {
  opacity: 1;
}

/* ---------- z5 点阵 canvas ---------- */
.intro-canvas {
  position: fixed;
  inset: 0;
  z-index: 5;
  width: 100%;
  height: 100%;
}

/* ---------- 右上角跳过 ---------- */
.skip-btn {
  position: fixed;
  top: var(--lx-space-4);
  right: var(--lx-space-4);
  z-index: 30;
  padding: var(--lx-space-1) var(--lx-space-3);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--lx-text-primary) 16%, transparent);
  border-radius: var(--lx-radius-pill);
  cursor: pointer;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-standard),
    border-color var(--lx-duration-fast) var(--lx-ease-standard);
}
.skip-btn:hover {
  color: var(--lx-text-primary);
  border-color: var(--lx-green);
}
.skip-btn:focus-visible {
  outline: 1px solid var(--lx-green);
  outline-offset: 2px;
}

/* ---------- z10 内容容器 ---------- */
.hero {
  position: relative;
  z-index: 10;
  width: min(100% - 48px, var(--lx-container-lg));
  margin: 0 auto;
  min-height: 100vh;
  min-height: 100svh;
  display: flex;
  align-items: center;
  padding: var(--lx-space-8) 0 var(--lx-space-6);
}
.hero-grid {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: center;
  gap: var(--lx-space-6);
  text-align: center;
}

/* ---------- 入场动画（复刻 harness .ds-hero-enter） ---------- */
.enter {
  animation: hero-enter 0.8s var(--lx-ease-out) backwards;
}
@keyframes hero-enter {
  0% {
    opacity: 0;
    transform: translateY(var(--enter-y, 20px));
    filter: blur(var(--enter-blur, 0px));
  }
  100% {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }
}

/* ---------- 左列文案 ---------- */
.hero-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--lx-space-5);
}
.hero-eyebrow {
  margin: 0 0 var(--lx-space-3);
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-md);
  letter-spacing: 0.08em;
  color: var(--lx-green);
}
.hero-title {
  margin: 0;
  font-size: clamp(28px, 4.4vw, 46px); /* 开屏豁免：对齐 harness 46px 大标题 */
  font-weight: var(--lx-font-semibold);
  line-height: var(--lx-leading-tight);
  letter-spacing: 0.2px;
  color: var(--lx-text-primary);
}
.enter-desc {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
  max-width: 580px;
}
.hero-desc {
  margin: 0;
  font-size: var(--lx-text-md);
  line-height: var(--lx-leading);
  color: var(--lx-text-secondary);
}
.enter-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--lx-space-3);
  margin-top: var(--lx-space-1);
}

/* ---------- 按钮（胶囊，复用全站令牌） ---------- */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--lx-space-3) var(--lx-space-5);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-medium);
  line-height: var(--lx-leading-tight);
  border-radius: var(--lx-radius-pill);
  cursor: pointer;
  transition:
    background var(--lx-duration-fast) var(--lx-ease-standard),
    border-color var(--lx-duration-fast) var(--lx-ease-standard),
    transform var(--lx-duration-fast) var(--lx-ease-standard);
}
.btn:active {
  transform: translateY(1px);
}
.btn:focus-visible {
  outline: 1px solid var(--lx-green);
  outline-offset: 3px;
}
.btn-primary {
  color: var(--lx-bg-page);
  background: var(--lx-green);
  border: 1px solid transparent;
}
.btn-primary:hover {
  background: var(--lx-green-light-3);
}
.btn-secondary {
  color: var(--lx-text-primary);
  background: color-mix(in srgb, var(--lx-text-primary) 6%, transparent);
  border: 1px solid color-mix(in srgb, var(--lx-text-primary) 15%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.btn-secondary:hover {
  border-color: color-mix(in srgb, var(--lx-text-primary) 34%, transparent);
}

/* ---------- 右列终端卡片 ---------- */
.term-card {
  width: min(424px, 100%);
  margin: 0 auto;
  background: color-mix(in srgb, var(--lx-bg-page) 20%, transparent);
  border: 1px solid color-mix(in srgb, var(--lx-text-primary) 8%, transparent);
  border-radius: var(--lx-radius-lg);
  box-shadow: var(--lx-shadow-3);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  overflow: hidden;
}
.term-tabs {
  display: flex;
  gap: var(--lx-space-1);
  padding: var(--lx-space-2) var(--lx-space-2) 0;
  border-bottom: 1px solid color-mix(in srgb, var(--lx-text-primary) 6%, transparent);
}
.term-tab {
  padding: var(--lx-space-1) var(--lx-space-4);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
  background: transparent;
  border: 1px solid transparent;
  border-bottom: 0;
  border-radius: var(--lx-radius-base) var(--lx-radius-base) 0 0;
  cursor: pointer;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-standard),
    background var(--lx-duration-fast) var(--lx-ease-standard),
    border-color var(--lx-duration-fast) var(--lx-ease-standard);
}
.term-tab:hover {
  color: var(--lx-text-primary);
}
.term-tab.on {
  color: var(--lx-text-primary);
  background: color-mix(in srgb, var(--lx-bg-page) 20%, transparent);
  border-color: color-mix(in srgb, var(--lx-text-primary) 8%, transparent);
}
.term-tab:focus-visible {
  outline: 1px solid var(--lx-green);
  outline-offset: -1px;
}
.term-bar {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  padding: var(--lx-space-3) var(--lx-space-4);
}
/* 三圆点用深色语义色（danger/warning/success），不引入新色 */
.term-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
}
.term-dot-close { background: var(--lx-danger); }
.term-dot-min { background: var(--lx-warning); }
.term-dot-max { background: var(--lx-success, var(--lx-green)); }
.term-title {
  margin-left: var(--lx-space-2);
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
}
.term-copy {
  margin-left: auto;
  padding: 0;
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: color var(--lx-duration-fast) var(--lx-ease-standard);
}
.term-copy:hover {
  color: var(--lx-text-primary);
}
.term-copy:focus-visible {
  outline: 1px solid var(--lx-green);
  outline-offset: 2px;
}
.term-body {
  padding: var(--lx-space-4);
}
.term-pre {
  margin: 0;
  min-height: 128px;
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-base);
  line-height: 1.7;
  color: var(--lx-text-primary);
  white-space: pre-wrap;
  word-break: break-all;
}
.term-prompt {
  margin-right: var(--lx-space-2);
  color: var(--lx-green);
  font-weight: var(--lx-font-semibold);
}
.term-ok {
  color: var(--lx-green);
}

/* 终端 tab 内容切换：只动 opacity */
.term-fade-enter-active,
.term-fade-leave-active {
  transition: opacity var(--lx-duration-base) var(--lx-ease-standard);
}
.term-fade-enter-from,
.term-fade-leave-to {
  opacity: 0;
}

/* ---------- 宽屏：左文右终端（与 harness 相同的 60/40 双栏） ---------- */
@media (min-width: 1080px) {
  .hero-grid {
    grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
    gap: var(--lx-space-8);
    text-align: left;
  }
  .hero-copy {
    align-items: flex-start;
    justify-content: center;
  }
  .hero-desc {
    text-align: left;
  }
  .enter-actions {
    justify-content: flex-start;
  }
}

/* ---------- 移动端 ---------- */
@media (max-width: 767px) {
  .hero {
    width: min(100% - 32px, var(--lx-container-lg));
    padding-top: var(--lx-space-8);
  }
  .hero-visual {
    width: min(560px, 130vw);
    margin-left: 0;
  }
  .hero-title {
    font-size: clamp(28px, 8.5vw, 36px);
  }
  .hero-desc {
    font-size: var(--lx-text-base);
  }
  .enter-actions {
    width: 100%;
    flex-direction: column;
  }
  .btn {
    width: 100%;
  }
  .skip-btn {
    top: var(--lx-space-3);
    right: var(--lx-space-3);
  }
}

/* 减少动态效果：不起循环动画，视觉直接可见 */
@media (prefers-reduced-motion: reduce) {
  .hero-visual {
    animation: none;
    opacity: 0.7;
    filter: none;
  }
  .hero-visual-drift,
  .intro-aurora::before,
  .intro-aurora::after {
    animation: none;
  }
  .enter {
    animation: none;
  }
  .hero-visual-img {
    opacity: 1;
  }
}
</style>

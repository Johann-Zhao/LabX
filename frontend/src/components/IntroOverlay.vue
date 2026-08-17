<script setup>
// ==========================================================================
// IntroOverlay —— 登录前多屏开屏动画（第十轮）
// 仿 deepseek.com/harness 整页结构：首屏 hero + 后续滚动叙事屏。
//   - 播放时机：登录前。未登录进入页面先看开屏，结束落 /login；
//     每次新的登录会话都播放（sessionStorage 只防同一标签页重复打断）。
//   - 首屏 1:1 仿 harness：深色暗场 + 90px 点阵 canvas + Seedream 视觉
//     screen 混合 + 内容 blur/y 依次入场 + 学生向终端卡片。
//   - 后续屏：IntersectionObserver 滚入淡入（对齐 harness whileInView）。
//   - prefers-reduced-motion：不起 canvas/循环动画/滚动动画，全部静态可见。
// ==========================================================================
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { currentUser } from '../store'

const router = useRouter()
const PLAYED_KEY = 'labx_intro_played' // 同标签页会话内已播过；新开页面重新播放

// ---------- 是否播放 ----------
const visible = ref(false)
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches

// ---------- 多屏叙事数据（除 hero / 结束屏外） ----------
const SECTIONS = [
  {
    id: 'why',
    num: '01',
    eyebrow: '为什么是 LabX',
    title: '实验室里最费时间的，是“东西在哪、怎么用”',
    text: '学生只需要说人话：借什么、想做什么、哪里不会。登记、推送、排障、经验沉淀，由 LabX 自动串起来。',
    cards: [
      { title: '借还不用贴标签', text: '借用记录就是去向，管理员随时知道谁在用、什么时候还。' },
      { title: '借走就有知识', text: '借一块开发板，自动收到它的说明书、接线图和避坑卡。' },
      { title: '经验留给下一个人', text: '归还时写两句心得，学长踩过的坑不再让人踩第二遍。' },
    ],
  },
  {
    id: 'flow',
    num: '02',
    eyebrow: '物料流转',
    title: '每一件物料，都有去处',
    text: '不贴任何实体标签。从借出到归还，借用记录就是物料去向；超期申请转人工审核，库存与在借数实时可查。',
    img: '/intro/scene-dark-1.png',
  },
  {
    id: 'knowledge',
    num: '03',
    eyebrow: '知识随行',
    title: '借什么，就学什么',
    text: '借走 Arduino，知识卡立刻跟上：它是什么、怎么接线、上手第一步、学长踩过的坑。知识不是躺在库里，而是跟着物料走。',
    img: '/intro/scene-dark-2.png',
  },
  {
    id: 'agent',
    num: '04',
    eyebrow: '智能助手',
    title: '从一句话，到一套方案',
    text: '“想做智能小车”“电机不转怎么办”“这板子能干嘛”——LabX 先澄清、再检索、后给可执行步骤，并标清每条经验的来源。',
    img: '/intro/scene-dark-3.png',
    cards: [
      { title: '愿望到方案', text: '说个想法，给完整物料清单、实施步骤和在库预约。' },
      { title: '智能排障', text: '描述现象，一步步排查，优先用实验室沉淀经验。' },
      { title: '物料求用法', text: '手里有板子不知道能干嘛？问它是什么、能做什么、怎么上手。' },
    ],
  },
]

const FINAL_CARDS = [
  { title: '借还闭环', text: '学生借还、管理员审核、库存实时可查。' },
  { title: '知识随行', text: '借物料自动推知识卡，归还心得沉淀进社区。' },
  { title: '智能助手', text: '问答、排障、愿望到方案，一个对话框全搞定。' },
]

// ---------- 学生向终端卡片（不出现 npm/git/开发者命令） ----------
const TERM_TABS = [
  {
    id: 'daily',
    label: '学生动线',
    title: 'LabX · 学生助手',
    lines: [
      { prompt: true, text: '借一块 Arduino' },
      { prompt: true, text: '归还时写两句心得' },
      { prompt: true, text: '问：电机不转怎么办？' },
      { ok: true, text: '✓ 去向、知识、经验自动串起来' },
    ],
  },
  {
    id: 'oneword',
    label: '一句话能力',
    title: 'LabX · 学生助手',
    lines: [
      { prompt: true, text: '想做一台智能小车' },
      { prompt: true, text: '这板子能干嘛？' },
      { prompt: true, text: '项目还差哪些物料？' },
      { ok: true, text: '✓ 给清单、给步骤、给经验来源' },
    ],
  },
]
const activeTermId = ref('daily')
const activeTerm = computed(() => TERM_TABS.find((t) => t.id === activeTermId.value) || TERM_TABS[0])
const copied = ref(false)
let copyTimer = 0

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

function cleanupAll() {
  stopCanvas()
  if (revealObserver) revealObserver.disconnect()
  if (railObserver) railObserver.disconnect()
  revealObserver = null
  railObserver = null
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('pointermove', onPointerMove)
  document.body.style.overflow = ''
}

// 结束开屏：本次会话标记已播；未登录落登录页（登录前开屏的固定收尾）
function finish() {
  if (leaving.value) return
  try { sessionStorage.setItem(PLAYED_KEY, '1') } catch { /* 写不进就算了 */ }
  cleanupAll()
  leaving.value = true
  if (!currentUser.role) router.push('/login')
  leaveTimer = setTimeout(() => { visible.value = false }, 400)
}

// 首屏副按钮：滚到下一屏继续看
function scrollToNext() {
  const sections = overlayRef.value?.querySelectorAll('.intro-section')
  if (!sections?.length) return
  const current = activeSection.value
  const target = sections[Math.min(current + 1, sections.length - 1)]
  target?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' })
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
  if (canvas.clientWidth !== canvasW || canvas.clientHeight !== canvasH) buildDots()

  gridCtx.clearRect(0, 0, canvasW, canvasH)

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

// ---------- 键盘跳过 ----------
function onKeydown(e) {
  if (e.key === 'Escape') finish()
}

// ---------- 滚动叙事：滚入淡入 + 右侧进度轨（仿 harness whileInView） ----------
const activeSection = ref(0)
let revealObserver = null
let railObserver = null

function initSectionFx() {
  const root = overlayRef.value
  if (!root || reducedMotion) return

  // 文案/图片块：滚入视口后加 .is-in，只播一次
  revealObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in')
          revealObserver.unobserve(entry.target)
        }
      }
    },
    { root, rootMargin: '0px 0px -10% 0px', threshold: 0.12 },
  )
  root.querySelectorAll('[data-rv]').forEach((el) => revealObserver.observe(el))

  // 进度轨：当前屏（约在视口中线附近）高亮
  const sections = [...root.querySelectorAll('.intro-section')]
  railObserver = new IntersectionObserver(
    (entries) => {
      let best = null
      for (const entry of entries) {
        if (entry.isIntersecting && (!best || entry.intersectionRatio > best.ratio)) {
          best = { ratio: entry.intersectionRatio, index: Number(entry.target.dataset.index) }
        }
      }
      if (best) activeSection.value = best.index
    },
    { root, rootMargin: '-45% 0px -45% 0px', threshold: [0, 0.2, 0.6, 1] },
  )
  sections.forEach((el, i) => {
    el.dataset.index = String(i)
    railObserver.observe(el)
  })
}

// ---------- 视觉图加载状态 ----------
const heroImgFailed = ref(false)
const heroImgLoaded = ref(false)
const failedImgs = ref(new Set())
function onHeroImgError() { heroImgFailed.value = true }
function onHeroImgLoad() { heroImgLoaded.value = true }
function onSceneImgError(src) { failedImgs.value = new Set(failedImgs.value).add(src) }

// ---------- 登录前重播 ----------
async function replay() {
  if (visible.value && !leaving.value) return
  leaving.value = false
  activeTermId.value = 'daily'
  copied.value = false
  activeSection.value = 0
  heroImgFailed.value = false
  heroImgLoaded.value = false
  failedImgs.value = new Set()
  mouseX = NaN
  mouseY = NaN
  visible.value = true
  await nextTick()
  if (!visible.value) return
  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', onKeydown)
  startCanvas()
  initSectionFx()
}

watch(
  () => currentUser.role,
  (role, prevRole) => {
    // 登出：回到登录前，再播一次开屏（对应"每次登录前都出现"）
    if (prevRole && !role) {
      try { sessionStorage.removeItem(PLAYED_KEY) } catch { /* 忽略 */ }
      replay()
    }
  },
)

// ---------- 挂载 / 卸载 ----------
onMounted(() => {
  // 未登录进入页面即播放（登录前开屏）；已登录刷新不打断工作流
  if (!currentUser.role) {
    try {
      if (sessionStorage.getItem(PLAYED_KEY) !== '1') replay()
    } catch {
      replay()
    }
  }
})

onBeforeUnmount(() => {
  clearTimeout(leaveTimer)
  clearTimeout(copyTimer)
  cleanupAll()
})
</script>

<template>
  <div
    v-if="visible"
    ref="overlayRef"
    class="intro-overlay"
    :class="{ 'is-leaving': leaving }"
    data-theme="dark"
  >
    <div class="intro-aurora" aria-hidden="true"></div>
    <canvas ref="canvasRef" class="intro-canvas" aria-hidden="true"></canvas>

    <button type="button" class="skip-btn" @click="finish">跳过</button>

    <!-- 右侧进度轨：首屏 + 4 个叙事屏 + 结束屏 -->
    <div class="rail" aria-hidden="true">
      <span
        v-for="i in SECTIONS.length + 2"
        :key="i"
        class="rail-node"
        :class="{ on: i - 1 === activeSection }"
      ></span>
    </div>

    <!-- ============ 首屏：1:1 仿 harness hero ============ -->
    <section class="intro-section hero-section" data-index="0">
      <!-- Seedream 主视觉：screen 混合 + 呼吸 + 鼠标视差 -->
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

      <div class="hero">
        <div class="hero-grid">
          <div class="hero-copy">
            <div class="enter" style="--enter-y: 24px; --enter-blur: 10px; animation-duration: 0.9s">
              <p class="hero-eyebrow lx-num">LABX // 高校创新空间</p>
              <h1 class="hero-title">物料有去处<br />知识有回路</h1>
            </div>
            <div class="enter enter-desc" style="--enter-y: 20px; --enter-blur: 8px; animation-delay: 0.15s">
              <p class="hero-desc">
                借物料、查知识、问排障、组项目，一个账号跑通实验室全流程。
              </p>
              <p class="hero-desc">
                不用贴标签，不用到处问学长，经验自动留给下一个人。
              </p>
            </div>
            <div class="enter enter-actions" style="--enter-y: 16px; animation-duration: 0.7s; animation-delay: 0.3s">
              <button type="button" class="btn btn-primary" @click="finish">进入登录</button>
              <button type="button" class="btn btn-secondary" @click="scrollToNext">往下看</button>
            </div>
          </div>

          <div class="enter enter-term" style="--enter-y: 20px; animation-duration: 0.9s; animation-delay: 0.4s">
            <div class="term-card">
              <div class="term-tabs" role="tablist" aria-label="学生场景终端">
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
      </div>
    </section>

    <!-- ============ 叙事屏 ============ -->
    <section
      v-for="(s, i) in SECTIONS"
      :key="s.id"
      class="intro-section narrative-section"
      :class="{ 'is-flip': i % 2 === 1 }"
      :data-index="i + 1"
    >
      <div class="section-inner" :class="s.img ? 'split-inner' : 'stack-inner'">
        <!-- 屏 1：为什么是 LabX（三张卡） -->
        <template v-if="s.id === 'why'">
          <div class="section-heading">
            <p class="section-eyebrow lx-num" data-rv>{{ s.num }} · {{ s.eyebrow }}</p>
            <h2 class="section-title" data-rv style="--rv-delay: 0.08s">{{ s.title }}</h2>
            <p class="section-text" data-rv style="--rv-delay: 0.16s">{{ s.text }}</p>
          </div>
          <div class="why-cards">
            <div v-for="(c, ci) in s.cards" :key="c.title" class="why-card" data-rv :style="{ '--rv-delay': `${0.2 + ci * 0.1}s` }">
              <h3 class="why-card-title">{{ c.title }}</h3>
              <p class="why-card-text">{{ c.text }}</p>
            </div>
          </div>
        </template>

        <!-- 屏 2-4：场景图 + 文案 -->
        <template v-else>
          <div class="scene-media" data-rv>
            <img
              v-if="s.img && !failedImgs.has(s.img)"
              class="scene-img"
              :src="s.img"
              alt=""
              @error="onSceneImgError(s.img)"
            />
          </div>
          <div class="section-copy">
            <p class="section-eyebrow lx-num" data-rv>{{ s.num }} · {{ s.eyebrow }}</p>
            <h2 class="section-title" data-rv style="--rv-delay: 0.08s">{{ s.title }}</h2>
            <p class="section-text" data-rv style="--rv-delay: 0.16s">{{ s.text }}</p>
            <div v-if="s.cards" class="mini-cards">
              <div v-for="(c, ci) in s.cards" :key="c.title" class="mini-card" data-rv :style="{ '--rv-delay': `${0.24 + ci * 0.1}s` }">
                <h3 class="mini-card-title">{{ c.title }}</h3>
                <p class="mini-card-text">{{ c.text }}</p>
              </div>
            </div>
          </div>
        </template>
      </div>
    </section>

    <!-- ============ 结束屏：进入登录 ============ -->
    <section class="intro-section final-section" :data-index="SECTIONS.length + 1">
      <div class="section-inner final-inner">
        <p class="section-eyebrow lx-num" data-rv>05 · 开始使用</p>
        <h2 class="section-title" data-rv style="--rv-delay: 0.08s">把你的下一个想法，带进实验室</h2>
        <p class="section-text" data-rv style="--rv-delay: 0.16s">登录后即可借物料、收知识卡、问 LabX。</p>
        <div class="final-cards">
          <div v-for="(c, ci) in FINAL_CARDS" :key="c.title" class="final-card" data-rv :style="{ '--rv-delay': `${0.2 + ci * 0.1}s` }">
            <h3 class="final-card-title">{{ c.title }}</h3>
            <p class="final-card-text">{{ c.text }}</p>
          </div>
        </div>
        <button type="button" class="btn btn-primary final-btn" data-rv style="--rv-delay: 0.5s" @click="finish">
          进入登录 →
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ============ 容器与背景 ============ */
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
  scrollbar-width: none;
}
.intro-overlay::-webkit-scrollbar {
  display: none;
}
.intro-overlay.is-leaving {
  opacity: 0;
  pointer-events: none;
}

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

.intro-canvas {
  position: fixed;
  inset: 0;
  z-index: 5;
  width: 100%;
  height: 100%;
  pointer-events: none; /* 鼠标坐标由 window 监听，canvas 本身不拦截滚动 */
}

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

.rail {
  position: fixed;
  right: var(--lx-space-5);
  top: 50%;
  transform: translateY(-50%);
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}
.rail-node {
  width: 2px;
  height: 18px;
  border-radius: var(--lx-radius-pill);
  background: var(--lx-border-strong);
  transition: background var(--lx-duration-base) var(--lx-ease-standard),
    transform var(--lx-duration-base) var(--lx-ease-standard);
}
.rail-node.on {
  background: var(--lx-green);
  transform: scaleY(1.5);
}

/* ============ 首屏 hero ============ */
.hero-section {
  position: relative;
  min-height: 100vh;
  min-height: 100svh;
  display: flex;
  align-items: center;
  overflow: hidden;
}

.hero-visual {
  position: absolute;
  left: 50%;
  top: 50%;
  z-index: 2;
  width: min(800px, 92vw);
  aspect-ratio: 1;
  margin-left: var(--lx-space-7);
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
  transform: translate3d(var(--intro-mx, 0px), var(--intro-my, 0px), 0);
}
.hero-visual.is-loaded .hero-visual-img {
  opacity: 1;
}

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
  font-size: clamp(28px, 4.4vw, 46px);
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

/* ============ 终端卡片（学生场景，无开发者命令） ============ */
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
  min-height: 118px;
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
.term-fade-enter-active,
.term-fade-leave-active {
  transition: opacity var(--lx-duration-base) var(--lx-ease-standard);
}
.term-fade-enter-from,
.term-fade-leave-to {
  opacity: 0;
}

/* ============ 叙事屏通用 ============ */
.narrative-section,
.final-section {
  position: relative;
  z-index: 10;
  min-height: 100vh;
  min-height: 100svh;
  display: flex;
  align-items: center;
  padding: var(--lx-space-8) 0;
}
.section-inner {
  width: min(100% - 48px, var(--lx-container-lg));
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--lx-space-6);
  text-align: center;
}
.section-heading,
.section-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--lx-space-3);
}
.section-eyebrow {
  margin: 0;
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-sm);
  letter-spacing: 0.12em;
  color: var(--lx-green);
}
.section-title {
  margin: 0;
  max-width: 760px;
  font-size: var(--lx-text-3xl);
  font-weight: var(--lx-font-semibold);
  line-height: var(--lx-leading-tight);
  letter-spacing: 0.4px;
  color: var(--lx-text-primary);
}
.section-text {
  margin: 0;
  max-width: 640px;
  font-size: var(--lx-text-md);
  line-height: var(--lx-leading);
  color: var(--lx-text-secondary);
}

/* 滚入动画：只在进入视口时上浮淡入一次（仿 harness whileInView） */
[data-rv] {
  opacity: 0;
  transform: translateY(28px);
  transition:
    opacity 0.6s var(--lx-ease-out),
    transform 0.6s var(--lx-ease-out);
  transition-delay: var(--rv-delay, 0s);
}
[data-rv].is-in {
  opacity: 1;
  transform: none;
}

/* 为什么 LabX：三张卡 */
.why-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--lx-space-4);
  width: 100%;
}
.why-card {
  padding: var(--lx-space-5);
  text-align: left;
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-md);
}
.why-card-title {
  margin: 0 0 var(--lx-space-2);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-green);
}
.why-card-text {
  margin: 0;
  font-size: var(--lx-text-sm);
  line-height: var(--lx-leading);
  color: var(--lx-text-regular);
}

/* 场景屏：图 + 文 */
.scene-media {
  width: 100%;
  opacity: 0.92;
}
.scene-img {
  width: 100%;
  height: auto;
  display: block;
  mix-blend-mode: screen; /* 图内黑底融入暗场，只留下发光主体 */
  border-radius: var(--lx-radius-lg);
}
.mini-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--lx-space-3);
  width: 100%;
  margin-top: var(--lx-space-3);
}
.mini-card {
  padding: var(--lx-space-4);
  text-align: left;
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-md);
}
.mini-card-title {
  margin: 0 0 var(--lx-space-1);
  font-size: var(--lx-text-sm);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-green);
}
.mini-card-text {
  margin: 0;
  font-size: var(--lx-text-xs);
  line-height: var(--lx-leading);
  color: var(--lx-text-regular);
}

/* ============ 结束屏 ============ */
.final-inner {
  max-width: 860px;
}
.final-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--lx-space-4);
  width: 100%;
}
.final-card {
  padding: var(--lx-space-5);
  text-align: left;
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-md);
}
.final-card-title {
  margin: 0 0 var(--lx-space-2);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-green);
}
.final-card-text {
  margin: 0;
  font-size: var(--lx-text-sm);
  line-height: var(--lx-leading);
  color: var(--lx-text-regular);
}
.final-btn {
  margin-top: var(--lx-space-2);
}

/* ============ 宽屏布局 ============ */
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

  .split-inner {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
    align-items: center;
    gap: var(--lx-space-8);
    text-align: left;
  }
  .split-inner .section-heading,
  .split-inner .section-copy {
    align-items: flex-start;
    text-align: left;
  }
  .is-flip .scene-media {
    order: 2;
  }
  .is-flip .section-copy {
    order: 1;
  }
}

/* ============ 移动端 ============ */
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
  .rail {
    right: var(--lx-space-2);
    gap: var(--lx-space-2);
  }
  .rail-node {
    height: 13px;
  }
  .narrative-section,
  .final-section {
    padding: var(--lx-space-7) 0;
  }
  .section-inner {
    width: min(100% - 32px, var(--lx-container-lg));
  }
  .section-title {
    font-size: var(--lx-text-2xl);
  }
  .section-text {
    font-size: var(--lx-text-base);
  }
  .why-cards,
  .mini-cards,
  .final-cards {
    grid-template-columns: minmax(0, 1fr);
  }
  .mini-cards {
    gap: var(--lx-space-2);
  }
}

/* 减少动态效果：静态可滚，内容全可见 */
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
  [data-rv] {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
</style>

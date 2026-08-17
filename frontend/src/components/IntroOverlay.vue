<script setup>
// ==========================================================================
// IntroOverlay —— 开屏滚动叙事页（学生端首次访问全屏播放）
// 2026 重做：仿 deepseek.com/harness 的"控制台化"动画风格（终端卡片 +
// 点阵粒子 + 流动波纹 + 微动效），但全套走浅色令牌（贴合项目浅色主基调，
// 不再强制 data-theme="dark"；跟随应用主题，默认浅色即浅色开屏）。
//
// 规则（队长拍板）：
// - 仅首次访问播放：localStorage 键 labx_intro_seen=1 标记已看；
//   /admin 不渲染本组件（App.vue 控制）；/login 允许播放（首访流程：动画 → 登录页）。
// - 5 屏滚动叙事：用户滚动驱动画面变化（类似 Apple 产品页）。滚动发生在
//   overlay 自己的滚动容器里，GSAP ScrollTrigger 的 scroller 指向它。
// - 右上角常驻"跳过"，Esc 也可跳过；不提供"点击任意处跳过"（与滚动冲突）。
// - prefers-reduced-motion：不建 ScrollTrigger、不起 canvas、不起波纹，
//   5 屏静态纵向堆叠，可正常滚动浏览（所有"初始隐藏"只由 GSAP 内联样式实现，
//   不建动画时内容天然全可见）。
// - 图片加载失败 @error 隐藏 <img>，只留文字 + 粒子背景（优雅降级）。
// - 注意：visible=false 只是收起模板，组件本体并不卸载，onBeforeUnmount
//   不一定触发——所有清理（含恢复 body 滚动）必须在 finish() 里就做掉。
// - 设计规范红线 9/14（禁滚动提示、禁循环动画）对本开屏豁免：这是队长
//   明确要的滚动叙事仪式感页面，普通页面仍按 docs/design/labx-ui.md 执行。
// ==========================================================================
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { currentUser } from '../store'

gsap.registerPlugin(ScrollTrigger)

const router = useRouter()

// ---------- 是否播放 ----------
const visible = ref(false)
try {
  visible.value = localStorage.getItem('labx_intro_seen') !== '1'
} catch {
  visible.value = false // 隐私模式等异常：不挡路，直接进主界面
}

// ---------- 5 屏内容 ----------
// 屏 2-4 的场景文案（屏 1 主视觉、屏 5 进入屏结构特殊，直接写在模板里）
const scenes = [
  {
    img: '/intro/scene1.png',
    hud: '01 / 物料流转',
    title: '每一件物料，都有去处',
    text: '借用记录即去向，不贴标签也能追踪',
  },
  {
    img: '/intro/scene2.png',
    hud: '02 / 知识随行',
    title: '每一次借用，都带来该学的知识',
    text: '借什么就推什么的说明书与避坑卡',
  },
  {
    img: '/intro/scene3.png',
    hud: '03 / 经验闭环',
    title: '每一次归还，经验都留给下一个人',
    text: '归还心得沉淀进社区，越用越聪明',
  },
]
// 屏 5 的三张能力卡
const cards = [
  { title: '愿望到方案', text: '说个想法，给你完整物料清单和实施步骤，在库物料一键预约' },
  { title: '智能排障', text: '电机不转？一步步带你排查，优先用实验室沉淀的经验' },
  { title: '物料求用法', text: '手里有板子不知道能干嘛？问它是什么、能做什么、怎么上手' },
]
const PANEL_COUNT = 5 // 进度轨节点数 = 屏数
const activePanel = ref(0) // 当前屏下标，驱动进度轨高亮

// img 加载失败时对应路径记入 failedImgs，模板里 v-if 隐藏图片（优雅降级）
const failedImgs = ref(new Set())
const onImgError = (src) => { failedImgs.value = new Set(failedImgs.value).add(src) }
// 图片加载完成后高度才确定，刷新一次 ScrollTrigger 让 scrub 区间重新测量
const onImgLoad = () => { if (!reducedMotion) ScrollTrigger.refresh() }

// 系统开了"减少动态效果"：不建 ScrollTrigger、不起 canvas、不起波纹
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ---------- 收尾 ----------
const leaving = ref(false) // 淡出中：加 class 播 400ms 渐隐，再收起 DOM
let leaveTimer = 0

// 统一清理：杀 ScrollTrigger、停 canvas、移监听、恢复 body 滚动。
// finish() 和 onBeforeUnmount 都会调它，幂等。
function cleanupAll() {
  if (gsapCtx) {
    gsapCtx.revert() // 还原所有 GSAP 动画与 ScrollTrigger（含内联样式）
    gsapCtx = null
  }
  stopCanvas()
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  // 组件不会真卸载，onBeforeUnmount 不一定触发——必须在这里就恢复主界面滚动
  document.body.style.overflow = ''
}

// 标记已看 + 清理 + 播整体淡出后收起 overlay；未登录则收尾落到登录页（首访流程：动画 → 登录）
function finish() {
  if (leaving.value) return // 防 Esc/按钮连点重复触发
  try { localStorage.setItem('labx_intro_seen', '1') } catch { /* 写不进就算了 */ }
  cleanupAll()
  leaving.value = true
  if (!currentUser.role) router.push('/login') // 已登录则原地不动
  // 等淡出动画（--lx-duration-slow 400ms）结束后再移除 DOM
  leaveTimer = setTimeout(() => { visible.value = false }, 400)
}

// ---------- 滚动叙事动画（GSAP ScrollTrigger） ----------
const scrollerRef = ref(null)
let gsapCtx = null

function initScrollFx() {
  const scroller = scrollerRef.value
  if (!scroller) return
  // context 作用域限定在滚动容器内选元素；revert() 可一键清掉全部动画
  gsapCtx = gsap.context(() => {
    // 屏 1：进场播一次（非滚动驱动），之后随滚动淡出上移
    gsap.from('.hero-inner > *', {
      opacity: 0, y: 32, duration: 1, ease: 'power2.out', stagger: 0.12,
    })
    gsap.to('.hero-inner', {
      y: -80, opacity: 0.15, ease: 'none',
      scrollTrigger: { scroller, trigger: '.panel-hero', start: 'top top', end: 'bottom top', scrub: true },
    })
    gsap.fromTo('.hero-img',
      { scale: 1.05 },
      {
        scale: 1, ease: 'none',
        scrollTrigger: { scroller, trigger: '.panel-hero', start: 'top top', end: 'bottom top', scrub: true },
      })

    // 屏 2-4：图片 scale 1.05→1 + 上下视差；HUD/标题/小字淡入上移
    gsap.utils.toArray('.panel-scene').forEach((panel) => {
      const img = panel.querySelector('.panel-img')
      if (img) {
        gsap.fromTo(img,
          { scale: 1.05, y: -40 },
          {
            scale: 1, y: 40, ease: 'none',
            // 从"屏顶进入视口底"到"屏底离开视口顶"全程 scrub
            scrollTrigger: { scroller, trigger: panel, start: 'top bottom', end: 'bottom top', scrub: true },
          })
      }
      gsap.fromTo(panel.querySelectorAll('.hud, .hud-line, .scene-title, .scene-text'),
        { opacity: 0, y: 36 },
        {
          opacity: 1, y: 0, stagger: 0.1, ease: 'none',
          scrollTrigger: { scroller, trigger: panel, start: 'top 78%', end: 'top 38%', scrub: true },
        })
    })

    // 屏 5：三张能力卡 + 进入按钮随滚动依次浮入
    gsap.fromTo('.panel-enter .cap-card, .panel-enter .enter-btn',
      { opacity: 0, y: 48 },
      {
        opacity: 1, y: 0, stagger: 0.12, ease: 'none',
        scrollTrigger: { scroller, trigger: '.panel-enter', start: 'top 82%', end: 'top 35%', scrub: true },
      })

    // 进度轨：屏中心区间被激活时高亮对应节点
    gsap.utils.toArray('.panel').forEach((panel, i) => {
      ScrollTrigger.create({
        scroller,
        trigger: panel,
        start: 'top center',
        end: 'bottom center',
        onToggle: (self) => { if (self.isActive) activePanel.value = i },
      })
    })
  }, scroller)
}

// ---------- canvas 点阵粒子背景（浅色化：淡绿小点 + 微弱连线，仿 harness 点阵） ----------
const canvasRef = ref(null)
let ctx = null
let rafId = 0
let particles = []
let lineColor = 'rgba(39, 121, 79, ' // 兜底：浅色 --lx-green #27794f

function particleCount() {
  const w = window.innerWidth
  if (w < 768) return 28 // 手机降档，省电不卡
  if (w < 1280) return 52
  return 76
}

function initParticles() {
  const canvas = canvasRef.value
  if (!canvas) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  particles = Array.from({ length: particleCount() }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.3, // 缓慢漂移（比星座更静，贴近 harness 的低干扰感）
    vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 1.3 + 0.6,
  }))
}

function drawFrame() {
  const canvas = canvasRef.value
  if (!canvas || !ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 粒子漂移 + 出界回绕
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    if (p.x < 0) p.x = canvas.width
    if (p.x > canvas.width) p.x = 0
    if (p.y < 0) p.y = canvas.height
    if (p.y > canvas.height) p.y = 0
  }

  // 微弱连线：距离近的粒子连线，越近越淡（浅色底上压低存在感）
  const LINK = 100
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.hypot(dx, dy)
      if (dist < LINK) {
        ctx.strokeStyle = lineColor + (0.16 * (1 - dist / LINK)).toFixed(3) + ')'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y)
        ctx.stroke()
      }
    }
  }

  // 画点
  for (const p of particles) {
    ctx.fillStyle = lineColor + '0.5)'
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fill()
  }

  rafId = requestAnimationFrame(drawFrame)
}

function stopCanvas() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
}

function onResize() {
  initParticles() // 窗口变化时重建粒子（数量随宽度档位变化）；ScrollTrigger 自己会处理 resize
}

// ---------- 键盘跳过（只留 Esc；空格是原生滚动键，不能抢） ----------
function onKeydown(e) {
  if (e.key === 'Escape') finish()
}

// ---------- 挂载 / 卸载 ----------
onMounted(() => {
  if (!visible.value) return
  document.body.style.overflow = 'hidden' // 锁主页面滚动，叙事在 overlay 自己的容器里滚
  window.addEventListener('keydown', onKeydown)

  if (!reducedMotion) {
    initScrollFx()
    const canvas = canvasRef.value
    if (canvas) {
      ctx = canvas.getContext('2d')
      // 线条颜色读取当前主题的 --lx-green（浅色主主题下是 #27794f，转成 rgba 前缀用）
      const green = getComputedStyle(canvas).getPropertyValue('--lx-green').trim()
      if (green) {
        const n = parseInt(green.slice(1), 16)
        lineColor = `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, `
      }
      initParticles()
      rafId = requestAnimationFrame(drawFrame)
      window.addEventListener('resize', onResize)
    }
  }
})

onBeforeUnmount(() => {
  clearTimeout(leaveTimer)
  cleanupAll()
})
</script>

<template>
  <!-- 不再强制 data-theme="dark"：跟随应用主题（默认浅色即浅色开屏） -->
  <div
    v-if="visible"
    class="intro-overlay"
    :class="{ 'is-leaving': leaving }"
  >
    <!-- 背景三层：蓝图网格（CSS）→ 流动波纹（CSS）→ 点阵粒子（canvas，最上层氛围） -->
    <div class="intro-grid" aria-hidden="true"></div>
    <div class="intro-wave" aria-hidden="true"></div>
    <canvas ref="canvasRef" class="intro-canvas" aria-hidden="true"></canvas>

    <button type="button" class="skip-btn" @click="finish">跳过</button>

    <!-- 右侧进度轨：5 节点，滚动高亮当前屏（纯指示，不可点） -->
    <div class="rail" aria-hidden="true">
      <span
        v-for="i in PANEL_COUNT"
        :key="i"
        class="rail-node"
        :class="{ on: i - 1 === activePanel }"
      ></span>
    </div>

    <!-- overlay 自己的滚动容器：ScrollTrigger 的 scroller 指向它 -->
    <div ref="scrollerRef" class="intro-scroller">
      <!-- 屏 1：主视觉（标题 + 控制台终端卡片，仿 harness 首屏左文右终端） -->
      <section class="panel panel-hero">
        <div class="panel-inner hero-inner">
          <div class="hero-copy">
            <h1 class="brand">LabX 创新空间</h1>
            <p class="brand-sub">高校创新空间的体验型智能体</p>
            <div class="scroll-hint" aria-hidden="true">
              <span class="scroll-hint-text">向下滚动</span>
              <span class="scroll-hint-arrow">↓</span>
            </div>
          </div>
          <!-- 终端卡片：macOS 三圆点 + 绿色 $ 前缀 + mono 命令（语义色，非新色） -->
          <div class="term-card" aria-hidden="true">
            <div class="term-bar">
              <span class="term-dot term-dot-close"></span>
              <span class="term-dot term-dot-min"></span>
              <span class="term-dot term-dot-max"></span>
              <span class="term-title">labx@console</span>
            </div>
            <div class="term-body">
              <p class="term-line"><span class="term-prompt">$</span> npm run dev</p>
              <p class="term-line"><span class="term-prompt">$</span> uvicorn main:app</p>
              <p class="term-line"><span class="term-prompt">$</span> 借块板子 → 推知识卡</p>
              <p class="term-line term-ok">✓ 15 件物料 · 33 张卡片在线</p>
            </div>
          </div>
          <img
            v-if="!failedImgs.has('/intro/hero.png')"
            class="panel-img hero-img"
            src="/intro/hero.png"
            alt=""
            @error="onImgError('/intro/hero.png')"
            @load="onImgLoad"
          />
        </div>
      </section>

      <!-- 屏 2-4：物料流转 / 知识随行 / 经验闭环 -->
      <section v-for="s in scenes" :key="s.hud" class="panel panel-scene">
        <div class="panel-inner">
          <p class="hud">{{ s.hud }}</p>
          <div class="hud-line" aria-hidden="true"></div>
          <img
            v-if="!failedImgs.has(s.img)"
            class="panel-img scene-img"
            :src="s.img"
            alt=""
            @error="onImgError(s.img)"
            @load="onImgLoad"
          />
          <h2 class="scene-title">{{ s.title }}</h2>
          <p class="scene-text">{{ s.text }}</p>
        </div>
      </section>

      <!-- 屏 5：能力卡 + 进入按钮 -->
      <section class="panel panel-enter">
        <div class="panel-inner enter-inner">
          <div class="cards">
            <div v-for="c in cards" :key="c.title" class="cap-card">
              <h3 class="cap-title">{{ c.title }}</h3>
              <p class="cap-text">{{ c.text }}</p>
            </div>
          </div>
          <button type="button" class="enter-btn" @click="finish">进入 LabX →</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* 颜色全部走浅色令牌（:root 默认即浅色主主题；跟随应用主题） */
.intro-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--lx-z-header); /* 100：压过学生端顶栏，不占 Element 弹层托管区 */
  background: var(--lx-bg-page); /* 浅色 #f7f7f4 暖白 */
  color: var(--lx-text-primary);
  font-family: var(--lx-font-sans);
  transition: opacity var(--lx-duration-slow) var(--lx-ease-standard);
}
.intro-overlay.is-leaving {
  opacity: 0;
  pointer-events: none; /* 淡出期间不再响应操作 */
}

/* 背景层 1：蓝图网格（复用令牌网格线，仿 harness 的点阵/网格底） */
.intro-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--lx-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--lx-grid-line) 1px, transparent 1px),
    linear-gradient(var(--lx-grid-line-fine) 1px, transparent 1px),
    linear-gradient(90deg, var(--lx-grid-line-fine) 1px, transparent 1px);
  background-size:
    var(--lx-grid-size) var(--lx-grid-size),
    var(--lx-grid-size) var(--lx-grid-size),
    var(--lx-grid-size-fine) var(--lx-grid-size-fine),
    var(--lx-grid-size-fine) var(--lx-grid-size-fine);
}

/* 背景层 2：流动波纹（软绿径向渐变，缓慢左右漂移；开屏豁免循环动画） */
.intro-wave {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.intro-wave::before,
.intro-wave::after {
  content: '';
  position: absolute;
  width: 120vw;
  height: 60vh;
  border-radius: 50%;
  filter: blur(60px);
}
.intro-wave::before {
  left: -30vw;
  top: -18vh;
  background: radial-gradient(closest-side, var(--lx-green-glow-soft), transparent 70%);
  animation: wave-drift 26s var(--lx-ease-standard) infinite alternate;
}
.intro-wave::after {
  right: -34vw;
  bottom: -20vh;
  background: radial-gradient(closest-side, var(--lx-green-glow-soft), transparent 70%);
  animation: wave-drift 34s var(--lx-ease-standard) infinite alternate-reverse;
}
@keyframes wave-drift {
  from { transform: translateX(-4vw) scale(1); }
  to { transform: translateX(4vw) scale(1.08); }
}

/* 点阵粒子：固定背景，不随叙事滚动 */
.intro-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.skip-btn {
  position: absolute;
  top: var(--lx-space-4);
  right: var(--lx-space-4);
  z-index: 3;
  padding: var(--lx-space-1) var(--lx-space-3);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
  background: transparent;
  border: 1px solid var(--lx-border-strong);
  border-radius: var(--lx-radius-base);
  cursor: pointer;
  transition: color var(--lx-duration-fast) var(--lx-ease-standard),
    border-color var(--lx-duration-fast) var(--lx-ease-standard);
}
.skip-btn:hover {
  color: var(--lx-text-primary);
  border-color: var(--lx-green);
}

/* 右侧进度轨：5 根细条，当前屏拉长变绿 */
.rail {
  position: absolute;
  right: var(--lx-space-5);
  top: 50%;
  transform: translateY(-50%);
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}
.rail-node {
  width: 2px;
  height: 24px;
  border-radius: var(--lx-radius-pill);
  background: var(--lx-border-strong);
  transition: background var(--lx-duration-base) var(--lx-ease-standard),
    transform var(--lx-duration-base) var(--lx-ease-standard);
}
.rail-node.on {
  background: var(--lx-green);
  transform: scaleY(1.4); /* 只动 transform，不引发布局抖动 */
}

/* overlay 自己的滚动容器：主页面被锁住，叙事在这里滚 */
.intro-scroller {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain; /* 滚到底不外泄给 body */
  scrollbar-width: thin;
  scrollbar-color: var(--lx-border-strong) transparent;
}

/* 每屏约 100vh，内容垂直居中 */
.panel {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--lx-space-7) var(--lx-space-5);
}
.panel-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--lx-space-4);
  max-width: 720px;
  text-align: center;
}

/* 屏 1：左文右终端（宽屏 ≥1024 并排；窄屏竖排） */
.hero-inner {
  max-width: 960px;
  gap: var(--lx-space-7);
}
@media (min-width: 1024px) {
  .hero-inner {
    flex-direction: row;
    text-align: left;
    align-items: center;
  }
  .hero-copy {
    flex: 1;
  }
  .term-card {
    flex: 1;
  }
}

/* 终端卡片：白底 + 细边框 + mono 命令，仿 harness 首屏控制台 */
.term-card {
  width: min(420px, 88vw);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-lg);
  box-shadow: var(--lx-shadow-2);
  text-align: left;
  overflow: hidden;
}
.term-bar {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  padding: var(--lx-space-2) var(--lx-space-3);
  background: var(--lx-bg-subtle);
  border-bottom: 1px solid var(--lx-border-light);
}
/* 三圆点用 LabX 语义色（danger/warning/success），不引入新色 */
.term-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.term-dot-close { background: var(--lx-danger); }
.term-dot-min { background: var(--lx-warning); }
.term-dot-max { background: var(--lx-success); }
.term-title {
  margin-left: var(--lx-space-2);
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
}
.term-body {
  padding: var(--lx-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
}
.term-line {
  margin: 0;
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-sm);
  line-height: var(--lx-leading);
  color: var(--lx-text-regular);
  word-break: break-all;
}
.term-prompt {
  color: var(--lx-green);
  font-weight: var(--lx-font-semibold);
}
.term-ok {
  color: var(--lx-green);
}

/* 图片：细边框 + 轻微绿色辉光（辉光色用 color-mix 从绿令牌兑出，不写死色值） */
.panel-img {
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-md);
  box-shadow: var(--lx-shadow-3),
    0 0 48px color-mix(in srgb, var(--lx-green) 12%, transparent);
  will-change: transform; /* scrub 期间持续动 transform，提前提示合成器 */
}
.hero-img {
  width: min(300px, 64vw);
}
.scene-img {
  width: min(460px, 88vw);
}

/* 屏 1 文字 */
.brand {
  margin: 0;
  font-size: var(--lx-text-4xl);
  font-weight: var(--lx-font-bold);
  line-height: var(--lx-leading-tight);
  letter-spacing: 2px;
}
.brand-sub {
  margin: 0;
  font-size: var(--lx-text-md);
  color: var(--lx-text-secondary);
}

/* 底部滚动提示：箭头呼吸起伏（reduced-motion 时全局 CSS 已把动画压成瞬时） */
.scroll-hint {
  margin-top: var(--lx-space-5);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--lx-space-1);
  color: var(--lx-text-placeholder);
}
.scroll-hint-text {
  font-size: var(--lx-text-xs);
  letter-spacing: 2px;
}
.scroll-hint-arrow {
  font-size: var(--lx-text-md);
  animation: hint-breathe 1.6s var(--lx-ease-standard) infinite;
}
@keyframes hint-breathe {
  0%, 100% { transform: translateY(0); opacity: 0.55; }
  50% { transform: translateY(6px); opacity: 1; }
}

/* HUD：等宽小编号 + 细线分隔 */
.hud {
  margin: 0;
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-sm);
  letter-spacing: 2px;
  color: var(--lx-green);
}
.hud-line {
  width: 48px;
  height: 1px;
  background: var(--lx-border-strong);
}

/* 屏 2-4 文字 */
.scene-title {
  margin: 0;
  font-size: var(--lx-text-3xl);
  font-weight: var(--lx-font-bold);
  line-height: var(--lx-leading-tight);
}
.scene-text {
  margin: 0;
  font-size: var(--lx-text-base);
  color: var(--lx-text-secondary);
}

/* 屏 5：三张能力卡 */
.enter-inner {
  max-width: 780px;
  gap: var(--lx-space-6);
}
.cards {
  display: flex;
  gap: var(--lx-space-4);
  width: 100%;
}
.cap-card {
  flex: 1;
  min-width: 0;
  padding: var(--lx-space-5);
  text-align: left;
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-md);
}
.cap-title {
  margin: 0 0 var(--lx-space-2);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-green);
}
.cap-text {
  margin: 0;
  font-size: var(--lx-text-sm);
  line-height: var(--lx-leading);
  color: var(--lx-text-regular);
}

.enter-btn {
  padding: var(--lx-space-3) var(--lx-space-7);
  font-size: var(--lx-text-lg);
  font-weight: var(--lx-font-medium);
  color: var(--lx-bg-page); /* 绿按钮上用暖白底做字色，对比度足够 */
  background: var(--lx-green);
  border: none;
  border-radius: var(--lx-radius-base);
  cursor: pointer;
  transition: background var(--lx-duration-fast) var(--lx-ease-standard);
}
.enter-btn:hover {
  background: var(--lx-green-light-3);
}
.enter-btn:active {
  transform: translateY(1px);
}

/* reduced-motion：关掉波纹（滚动叙事与粒子已由 JS 跳过） */
@media (prefers-reduced-motion: reduce) {
  .intro-wave::before,
  .intro-wave::after {
    animation: none;
  }
}

/* 移动端：375px 下字号降档、能力卡竖排、进度轨简化 */
@media (max-width: 767px) {
  .panel {
    padding: var(--lx-space-6) var(--lx-space-4);
  }
  .brand {
    font-size: var(--lx-text-3xl);
  }
  .brand-sub {
    font-size: var(--lx-text-base);
  }
  .scene-title {
    font-size: var(--lx-text-2xl);
  }
  .scene-text {
    font-size: var(--lx-text-sm);
  }
  .cards {
    flex-direction: column;
  }
  .rail {
    right: var(--lx-space-2);
    gap: var(--lx-space-2);
  }
  .rail-node {
    height: 16px;
  }
  .skip-btn {
    top: var(--lx-space-3);
    right: var(--lx-space-3);
  }
  .hero-inner {
    gap: var(--lx-space-5);
  }
}
</style>

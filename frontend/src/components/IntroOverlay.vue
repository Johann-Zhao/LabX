<script setup>
// ==========================================================================
// IntroOverlay —— 开屏深色介绍动画（学生端首次访问全屏播放）
// 规则（队长拍板）：
// - 仅首次访问播放：localStorage 键 labx_intro_seen=1 标记已看；
// - 右上角常驻"跳过"；点击/ Esc / Enter / 空格 也可跳过；
// - 4 幕自动推进（前 3 幕各 2.2s，第 4 幕停在结束卡等用户点"进入 LabX"）；
// - prefers-reduced-motion：跳过动画与 canvas，直接显示结束卡；
// - 图片未生成时 @error 隐藏 <img>，只留文字 + 粒子背景，动画照样完整。
// ==========================================================================
import { onBeforeUnmount, onMounted, ref } from 'vue'

// ---------- 是否播放 ----------
// /admin 不渲染本组件（App.vue 控制）；这里只管"首次访问"判断
const visible = ref(false)
try {
  visible.value = localStorage.getItem('labx_intro_seen') !== '1'
} catch {
  visible.value = false // 隐私模式等异常：不挡路，直接进主界面
}

// ---------- 4 幕内容 ----------
// img 加载失败时对应下标记入 failedImgs，模板里 v-if 隐藏图片（优雅降级）
const scenes = [
  { img: '/intro/hero.png', title: 'LabX 创新空间', text: '' },
  { img: '/intro/scene1.png', title: '', text: '每一件物料，都有去处' },
  { img: '/intro/scene2.png', title: '', text: '每一次借用，都带来该学的知识' },
  { img: '/intro/scene3.png', title: '', text: '每一次归还，经验都留给下一个人' },
]
const scene = ref(0) // 当前幕下标 0-3
const failedImgs = ref(new Set())
const onImgError = (i) => failedImgs.value = new Set(failedImgs.value).add(i)

// 系统开了"减少动态效果"：不播动画、不起 canvas，直接停在结束卡
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ---------- 定时器与收尾 ----------
let timers = []
const leaving = ref(false) // 淡出中：加 class 播 400ms 渐隐，再真正卸载

// 标记已看 + 播整体淡出动画后卸载 overlay
function finish() {
  try { localStorage.setItem('labx_intro_seen', '1') } catch { /* 写不进就算了 */ }
  clearTimers()
  stopCanvas()
  // 注意：visible=false 只是收起模板里的根 div，组件本体并不卸载，
  // onBeforeUnmount 不会触发——必须在这里就恢复主界面滚动
  document.body.style.overflow = ''
  leaving.value = true
  // 等淡出动画（--lx-duration-slow 400ms）结束后再移除 DOM
  setTimeout(() => { visible.value = false }, 400)
}
function clearTimers() {
  timers.forEach(clearTimeout)
  timers = []
}

// 自动推进：前 3 幕各停留 2.2s，第 6.6s 进入结束卡（总时长 ≤8s 的约定）
const SCENE_MS = 2200
function startTimeline() {
  if (reducedMotion) {
    scene.value = scenes.length - 1 // 直接显示结束卡
    return
  }
  for (let i = 1; i < scenes.length; i++) {
    timers.push(setTimeout(() => { scene.value = i }, SCENE_MS * i))
  }
}

// ---------- canvas 粒子 / 电路线条背景 ----------
// 原生 canvas，无依赖；粒子数按设备宽度降档；颜色读深色令牌 --lx-green
const canvasRef = ref(null)
let ctx = null
let rafId = 0
let particles = []
let lineColor = 'rgba(93, 154, 123, ' // 兜底：深色 --lx-green #5d9a7b

function particleCount() {
  const w = window.innerWidth
  if (w < 768) return 36 // 手机降档，省电不卡
  if (w < 1280) return 64
  return 90
}

function initParticles() {
  const canvas = canvasRef.value
  if (!canvas) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  particles = Array.from({ length: particleCount() }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.4, // 缓慢漂移
    vy: (Math.random() - 0.5) * 0.4,
    r: Math.random() * 1.6 + 0.8,
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

  // 电路线条：距离近的粒子连线，越近越亮
  const LINK = 120
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x
      const dy = particles[i].y - particles[j].y
      const dist = Math.hypot(dx, dy)
      if (dist < LINK) {
        ctx.strokeStyle = lineColor + (0.28 * (1 - dist / LINK)).toFixed(3) + ')'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(particles[i].x, particles[i].y)
        ctx.lineTo(particles[j].x, particles[j].y)
        ctx.stroke()
      }
    }
  }

  // 画粒子
  for (const p of particles) {
    ctx.fillStyle = lineColor + '0.7)'
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
  initParticles() // 窗口变化时重建粒子（数量随宽度档位变化）
}

// ---------- 键盘跳过 ----------
function onKeydown(e) {
  if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') finish()
}

// ---------- 挂载 / 卸载 ----------
onMounted(() => {
  if (!visible.value) return
  document.body.style.overflow = 'hidden' // 动画期间禁止滚动
  window.addEventListener('keydown', onKeydown)
  startTimeline()

  if (!reducedMotion) {
    const canvas = canvasRef.value
    if (canvas) {
      ctx = canvas.getContext('2d')
      // 线条颜色跟随深色令牌 --lx-green（读出来是 hex，转成 rgba 前缀用）
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
  clearTimers()
  stopCanvas()
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  document.body.style.overflow = '' // 恢复主界面滚动
})
</script>

<template>
  <!-- data-theme="dark"：整块走 tokens.css 深色令牌；点击任意处也可跳过 -->
  <div
    v-if="visible"
    class="intro-overlay"
    :class="{ 'is-leaving': leaving }"
    data-theme="dark"
    @click="finish"
  >
    <canvas ref="canvasRef" class="intro-canvas" aria-hidden="true"></canvas>

    <button type="button" class="skip-btn" @click.stop="finish">跳过</button>

    <!-- :key 换幕时重建 DOM，让入场 keyframes 每幕重播 -->
    <div :key="scene" class="scene">
      <img
        v-if="scenes[scene].img && !failedImgs.has(scene)"
        class="scene-img"
        :class="{ hero: scene === 0 }"
        :src="scenes[scene].img"
        alt=""
        @error="onImgError(scene)"
      />
      <h1 v-if="scenes[scene].title" class="brand">{{ scenes[scene].title }}</h1>
      <p v-if="scenes[scene].text" class="scene-text">{{ scenes[scene].text }}</p>
      <button
        v-if="scene === scenes.length - 1"
        type="button"
        class="enter-btn"
        @click.stop="finish"
      >
        进入 LabX →
      </button>
    </div>

    <!-- 进度点：表达真实播放进度（规范允许的唯一圆点用途） -->
    <div class="progress" aria-hidden="true">
      <span
        v-for="(s, i) in scenes"
        :key="i"
        class="dot"
        :class="{ on: i === scene }"
      ></span>
    </div>
  </div>
</template>

<style scoped>
/* 颜色全部走深色令牌（本组件根元素挂了 data-theme="dark"） */
.intro-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--lx-z-header); /* 100：压过学生端顶栏，不占 Element 弹层托管区 */
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lx-bg-page); /* #101613 墨绿近黑 */
  color: var(--lx-text-primary);
  font-family: var(--lx-font-sans);
  cursor: pointer;
  transition: opacity var(--lx-duration-slow) var(--lx-ease-standard);
}
.intro-overlay.is-leaving {
  opacity: 0;
  pointer-events: none; /* 淡出期间不再响应点击 */
}

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
  z-index: 1;
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

/* 每幕入场：淡入 + 上移（规范允许的 transform/opacity 动效） */
.scene {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--lx-space-5);
  padding: 0 var(--lx-space-5);
  max-width: 640px;
  text-align: center;
  animation: scene-in var(--lx-duration-slow) var(--lx-ease-out) both;
}
@keyframes scene-in {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.scene-img {
  max-width: 100%;
  width: 420px;
  border-radius: var(--lx-radius-md);
  border: 1px solid var(--lx-border);
}
.scene-img.hero {
  width: 300px; /* 主视觉图略小，突出大号字标 */
}

.brand {
  margin: 0;
  font-size: var(--lx-text-4xl);
  font-weight: var(--lx-font-bold);
  line-height: var(--lx-leading-tight);
  letter-spacing: 2px;
}

.scene-text {
  margin: 0;
  font-size: var(--lx-text-2xl);
  font-weight: var(--lx-font-semibold);
  line-height: var(--lx-leading-tight);
}

.enter-btn {
  padding: var(--lx-space-3) var(--lx-space-6);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-medium);
  color: var(--lx-bg-page); /* 深底上的绿按钮：用页面底色做字色，对比度足够 */
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

/* 进度点：4 个，当前幕点亮 */
.progress {
  position: absolute;
  bottom: var(--lx-space-6);
  display: flex;
  gap: var(--lx-space-2);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: var(--lx-radius-pill);
  background: var(--lx-border-strong);
  transition: background var(--lx-duration-base) var(--lx-ease-standard);
}
.dot.on {
  background: var(--lx-green);
}

/* 移动端：375px 下字标/文案降一档，不溢出 */
@media (max-width: 767px) {
  .brand {
    font-size: var(--lx-text-3xl);
  }
  .scene-text {
    font-size: var(--lx-text-xl);
  }
  .scene-img.hero {
    width: 220px;
  }
}
</style>

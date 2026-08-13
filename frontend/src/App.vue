<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchUsers } from './api'
import { currentUser, logout } from './store'
import IntroOverlay from './components/IntroOverlay.vue'

const route = useRoute()
const router = useRouter()
// 管理台独立布局：/admin 下不渲染学生端外壳（顶栏 + 导航 tabs），直接显示 AdminPage
const isAdmin = computed(() => route.path.startsWith('/admin'))
// 登录页同样无外壳（全屏居中卡）
const isLogin = computed(() => route.path === '/login')
const bare = computed(() => isAdmin.value || isLogin.value)

const users = ref([])

// 主题切换：深色/浅色一键（默认浅色，用户选择存 localStorage）
const isDark = ref(document.documentElement.dataset.theme === 'dark')
function toggleTheme() {
  const next = !isDark.value
  isDark.value = next
  document.documentElement.dataset.theme = next ? 'dark' : ''
  localStorage.setItem('labx_theme', next ? 'dark' : 'light')
}

function onLogout() {
  logout()
  router.push('/login')
}

onMounted(async () => {
  const res = await fetchUsers()
  if (res.code === 0) users.value = res.data
})
</script>

<template>
  <template v-if="!bare">
    <header class="topbar">
      <!-- 字标组合：LABX mono 小标 + 细分隔竖线 + 中文主标 -->
      <div class="brand">
        <span class="brand-mark">LABX</span>
        <span class="brand-sep" aria-hidden="true"></span>
        <span class="brand-name">创新空间</span>
      </div>
      <div class="topbar-side">
        <span class="user-label lx-num" aria-hidden="true">用户</span>
        <span class="user-name">{{ currentUser.name }}</span>
        <span class="role-badge lx-num">{{ currentUser.role === 'admin' ? '管理员' : '学生' }}</span>
        <button
          type="button"
          class="logout-btn theme-btn"
          :title="isDark ? '切换到浅色' : '切换到深色'"
          @click="toggleTheme"
        >
          {{ isDark ? '浅色' : '深色' }}
        </button>
        <button type="button" class="logout-btn" @click="onLogout">退出</button>
      </div>
    </header>

    <!-- 仪器状态行：mono 状态文本 + 细发线（USERS 数是真实用户列表长度） -->
    <div class="statusline" aria-hidden="true">
      <span class="status-text lx-num">系统就绪<template v-if="users.length"> · 用户 {{ users.length }}</template></span>
      <span class="status-rule"></span>
    </div>

    <nav class="tabs">
      <router-link to="/" class="tab" exact-active-class="active">
        <span class="tab-zh">智能助手</span>
      </router-link>
      <router-link to="/materials" class="tab" active-class="active">
        <span class="tab-zh">物料</span>
      </router-link>
      <router-link to="/records" class="tab" active-class="active">
        <span class="tab-zh">我的借用</span>
      </router-link>
      <router-link v-if="currentUser.role === 'admin'" to="/admin" class="tab" active-class="active">
        <span class="tab-zh">管理</span>
      </router-link>
    </nav>

    <!-- 移动端底部 tab 栏：<768px 常驻底部，单手可达；宽屏隐藏 -->
    <nav class="mobile-tabs" aria-label="移动端导航">
      <router-link to="/" class="mtab" exact-active-class="active">
        <span class="mtab-zh">助手</span>
      </router-link>
      <router-link to="/materials" class="mtab" active-class="active">
        <span class="mtab-zh">物料</span>
      </router-link>
      <router-link to="/records" class="mtab" active-class="active">
        <span class="mtab-zh">借用</span>
      </router-link>
      <router-link v-if="currentUser.role === 'admin'" to="/admin" class="mtab" active-class="active">
        <span class="mtab-zh">管理</span>
      </router-link>
    </nav>
  </template>

  <router-view />

  <!-- 开屏介绍动画：仅学生端首次访问播放（/admin 永不渲染；组件内部用 localStorage 控仅首次） -->
  <IntroOverlay v-if="!isAdmin" />
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--lx-space-2);
  padding: var(--lx-space-2) 0;
}
/* 字标组合：mono 小标 LABX + 细竖线 + 中文主标 */
.brand {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  min-width: 0;
}
.brand-mark {
  font-family: var(--lx-font-mono);
  font-size: var(--lx-text-lg);
  font-weight: var(--lx-font-bold);
  letter-spacing: 0.1em;
  color: var(--lx-green);
  line-height: var(--lx-leading-tight);
}
.brand-sep {
  width: 1px;
  height: var(--lx-space-4);
  background: var(--lx-border-strong);
  flex-shrink: 0;
}
.brand-name {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
  white-space: nowrap;
}
.topbar-side {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  flex-shrink: 0;
}
.user-label {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}
.user-name {
  font-size: var(--lx-text-base);
  font-weight: var(--lx-font-medium);
  color: var(--lx-text-primary);
  white-space: nowrap;
}
/* role 徽标：mono 小字 + 浅绿底（管理端同一套令牌语言） */
.role-badge {
  padding: 1px var(--lx-space-2);
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-green);
  background: var(--lx-green-light-9);
  border: 1px solid var(--lx-green-light-8);
  border-radius: var(--lx-radius-sm);
}
.logout-btn {
  padding: var(--lx-space-1) var(--lx-space-2);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
  background: transparent;
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-base);
  cursor: pointer;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    border-color var(--lx-duration-fast) var(--lx-ease-out);
}
.logout-btn:hover {
  color: var(--lx-danger);
  border-color: var(--lx-danger);
}

/* 仪器状态行：mono 状态文本贴左，细发线拉满剩余宽度 */
.statusline {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  margin-bottom: var(--lx-space-3);
}
.status-text {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.08em;
  color: var(--lx-text-placeholder);
  white-space: nowrap;
}
.status-rule {
  flex: 1;
  height: 1px;
  background: var(--lx-border-light);
}

/* 分段控件风 tabs：浅底槽 + 细边框，激活段浮白卡 + 主绿文字 */
.tabs {
  display: flex;
  gap: var(--lx-space-1);
  padding: var(--lx-space-1);
  margin-bottom: var(--lx-space-3);
  background: var(--lx-bg-subtle);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--lx-space-1) var(--lx-space-3);
  border: 1px solid transparent;
  border-radius: var(--lx-radius-base);
  color: var(--lx-text-secondary);
  text-decoration: none;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    background-color var(--lx-duration-fast) var(--lx-ease-out),
    border-color var(--lx-duration-fast) var(--lx-ease-out);
}
.tab-zh {
  font-size: var(--lx-text-base);
  line-height: var(--lx-leading-tight);
}
/* mono 功能小标签：真实路由标识（Linear 的 FIG/ENG 式标注），窄屏隐藏保紧凑 */
.tab-en {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.12em;
  line-height: var(--lx-leading-tight);
  color: var(--lx-text-placeholder);
  transition: color var(--lx-duration-fast) var(--lx-ease-out);
}
.tab:hover {
  background: var(--lx-bg-hover);
  color: var(--lx-text-primary);
}
.tab.active {
  background: var(--lx-bg-surface);
  border-color: var(--lx-green-light-7);
  box-shadow: 0 0 0 1px var(--lx-green-light-8), 0 2px 8px var(--lx-green-glow-soft);
  color: var(--lx-green);
  font-weight: var(--lx-font-medium);
}
.tab.active .tab-en {
  color: var(--lx-green);
}

/* ---------- 移动端底部 tab 栏 ---------- */
.mobile-tabs {
  display: none;
}
@media (max-width: 767px) {
  .mobile-tabs {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--lx-bg-surface);
    border-top: 1px solid var(--lx-border-light);
    box-shadow: 0 -2px 8px rgba(28, 35, 32, 0.04);
    z-index: var(--lx-z-header);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .mtab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: var(--lx-space-1) 0;
    color: var(--lx-text-secondary);
    text-decoration: none;
    font-size: var(--lx-text-xs);
  }
  .mtab-en {
    font-size: 10px;
    letter-spacing: 0.1em;
    color: var(--lx-text-placeholder);
  }
  .mtab.active {
    color: var(--lx-green);
    font-weight: var(--lx-font-medium);
  }
  .mtab.active .mtab-en {
    color: var(--lx-green);
  }
}

/* 窄屏：mono 小标与 USER 标注收起，控件不挤 */
@media (max-width: 767px) {
  .tab-en {
    display: none;
  }
  .tab {
    padding: var(--lx-space-2) var(--lx-space-2);
  }
}
@media (max-width: 480px) {
  .user-label {
    display: none;
  }
}
</style>

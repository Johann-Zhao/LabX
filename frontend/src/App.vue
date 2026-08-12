<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchUsers } from './api'
import { currentUser, setUser } from './store'
import IntroOverlay from './components/IntroOverlay.vue'

const route = useRoute()
// 管理台独立布局：/admin 下不渲染学生端外壳（顶栏 + 导航 tabs），直接显示 AdminPage
const isAdmin = computed(() => route.path.startsWith('/admin'))

const users = ref([])

// el-select 双向绑定的代理：读当前用户，写时切换全局状态
const selectedUserId = computed({
  get: () => currentUser.id,
  set: (userId) => {
    const u = users.value.find((x) => x.user_id === userId)
    if (u) setUser({ id: u.user_id, name: u.name })
  },
})

onMounted(async () => {
  const res = await fetchUsers()
  if (res.code === 0) users.value = res.data
})
</script>

<template>
  <template v-if="!isAdmin">
    <header class="topbar">
      <!-- 字标组合：LABX mono 小标 + 细分隔竖线 + 中文主标 -->
      <div class="brand">
        <span class="brand-mark">LABX</span>
        <span class="brand-sep" aria-hidden="true"></span>
        <span class="brand-name">创新空间</span>
      </div>
      <div class="topbar-side">
        <span class="user-label lx-num" aria-hidden="true">USER</span>
        <el-select v-model="selectedUserId" size="small" class="user-switch">
          <el-option
            v-for="u in users"
            :key="u.user_id"
            :label="`${u.name}（${u.user_id}）`"
            :value="u.user_id"
          />
        </el-select>
      </div>
    </header>

    <!-- 仪器状态行：mono 状态文本 + 细发线（USERS 数是真实用户列表长度） -->
    <div class="statusline" aria-hidden="true">
      <span class="status-text lx-num">SYS READY<template v-if="users.length"> · USERS {{ users.length }}</template></span>
      <span class="status-rule"></span>
    </div>

    <nav class="tabs">
      <router-link to="/" class="tab" exact-active-class="active">
        <span class="tab-zh">智能助手</span>
        <span class="tab-en lx-num" aria-hidden="true">AGENT</span>
      </router-link>
      <router-link to="/materials" class="tab" active-class="active">
        <span class="tab-zh">物料</span>
        <span class="tab-en lx-num" aria-hidden="true">MAT</span>
      </router-link>
      <router-link to="/records" class="tab" active-class="active">
        <span class="tab-zh">我的借用</span>
        <span class="tab-en lx-num" aria-hidden="true">REC</span>
      </router-link>
      <router-link to="/admin" class="tab" active-class="active">
        <span class="tab-zh">管理</span>
        <span class="tab-en lx-num" aria-hidden="true">ADMIN</span>
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
.user-switch {
  width: 170px;
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
  padding: var(--lx-space-1) var(--lx-space-2);
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
  border-color: var(--lx-border);
  box-shadow: var(--lx-shadow-1);
  color: var(--lx-green);
  font-weight: var(--lx-font-medium);
}
.tab.active .tab-en {
  color: var(--lx-green);
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

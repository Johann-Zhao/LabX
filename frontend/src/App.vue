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
      <span class="logo">LabX 创新空间</span>
      <el-select v-model="selectedUserId" size="small" class="user-switch">
        <el-option
          v-for="u in users"
          :key="u.user_id"
          :label="`${u.name}（${u.user_id}）`"
          :value="u.user_id"
        />
      </el-select>
    </header>

    <nav class="tabs">
      <router-link to="/" class="tab" exact-active-class="active">物料</router-link>
      <router-link to="/ask" class="tab" active-class="active">智能助手</router-link>
      <router-link to="/records" class="tab" active-class="active">我的借用</router-link>
      <router-link to="/admin" class="tab" active-class="active">管理</router-link>
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
  padding: 8px 4px 12px;
}
.logo {
  font-size: 20px;
  font-weight: bold;
  color: #42b883;
}
.user-switch {
  width: 170px;
}
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  border-radius: 8px;
  background: #fff;
  color: #606266;
  text-decoration: none;
  font-size: 14px;
}
.tab.active {
  background: #42b883;
  color: #fff;
  font-weight: bold;
}
</style>

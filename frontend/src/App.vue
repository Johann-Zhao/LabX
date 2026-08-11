<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchUsers } from './api'
import { currentUser, setUser } from './store'

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
    <router-link to="/bom" class="tab" active-class="active">愿望到方案</router-link>
    <router-link to="/ask" class="tab" active-class="active">问答</router-link>
    <router-link to="/records" class="tab" active-class="active">我的借用</router-link>
  </nav>

  <router-view />
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

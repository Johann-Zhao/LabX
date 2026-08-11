<script setup>
import { currentUser } from './store'
</script>

<template>
  <header class="topbar">
    <span class="logo">LabX 创新空间</span>
    <span class="user">{{ currentUser.name }}（{{ currentUser.id }}）</span>
  </header>

  <nav class="tabs">
    <router-link to="/" class="tab" exact-active-class="active">物料</router-link>
    <router-link to="/records" class="tab" active-class="active">我的借用</router-link>
  </nav>

  <router-view />
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 8px 4px 12px;
}
.logo {
  font-size: 20px;
  font-weight: bold;
  color: #42b883;
}
.user {
  font-size: 13px;
  color: #909399;
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
  font-size: 15px;
}
.tab.active {
  background: #42b883;
  color: #fff;
  font-weight: bold;
}
</style>

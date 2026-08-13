<script setup>
// 登录页：学号 + 密码（API.md 第 9.1 节）。
// 成功按 role 分流：admin → /admin，student → /；失败统一展示接口 msg（1008，不区分原因）。
// 视觉走仪器控制台风：全屏居中卡 + lx-brackets 角标 + mono HUD 标签，不加新依赖。
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api'
import { setUser } from '../store'

const router = useRouter()
const userId = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function onSubmit() {
  if (loading.value) return
  if (!userId.value || !password.value) {
    errorMsg.value = '请输入学号和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await login(userId.value, password.value)
    if (res.code === 0) {
      setUser({ id: res.data.user_id, name: res.data.name, role: res.data.role })
      router.push(res.data.role === 'admin' ? '/admin' : '/')
    } else {
      errorMsg.value = res.msg
    }
  } catch {
    errorMsg.value = '网络错误，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card lx-brackets">
      <div class="hud lx-num">LABX ACCESS</div>
      <h1 class="title">登录创新空间</h1>
      <p class="sub">学号 + 密码，进入你的实验台</p>

      <form class="form" @submit.prevent="onSubmit">
        <label class="field">
          <span class="field-label lx-num">ID</span>
          <input
            v-model.trim="userId"
            class="field-input lx-num"
            type="text"
            placeholder="学号 / 账号"
            autocomplete="username"
          />
        </label>
        <label class="field">
          <span class="field-label lx-num">KEY</span>
          <input
            v-model="password"
            class="field-input"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
          />
        </label>

        <p v-if="errorMsg" class="error" role="alert">{{ errorMsg }}</p>

        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? '验证中…' : '进入 LabX →' }}
        </button>
      </form>

      <p class="demo-hint lx-num">DEMO · 2024001 / 123456（学生） · admin / admin888（管理）</p>
    </div>
  </div>
</template>

<style scoped>
/* 纵向居中：#app 有上下内边距，扣掉后大致满屏居中 */
.login-wrap {
  min-height: calc(100vh - 140px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card {
  width: min(400px, 100%);
  padding: var(--lx-space-6);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-lg);
  box-shadow: var(--lx-shadow-2);
}
.hud {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.14em;
  color: var(--lx-green);
}
.title {
  margin: var(--lx-space-2) 0 0;
  font-size: var(--lx-text-2xl);
  font-weight: var(--lx-font-bold);
  line-height: var(--lx-leading-tight);
}
.sub {
  margin: var(--lx-space-1) 0 var(--lx-space-5);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-1);
}
.field-label {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.12em;
  color: var(--lx-text-placeholder);
}
.field-input {
  padding: var(--lx-space-2) var(--lx-space-3);
  font-size: var(--lx-text-base);
  font-family: var(--lx-font-sans);
  color: var(--lx-text-primary);
  background: var(--lx-bg-page);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-base);
  outline: none;
  transition:
    border-color var(--lx-duration-fast) var(--lx-ease-out),
    box-shadow var(--lx-duration-fast) var(--lx-ease-out);
}
.field-input::placeholder {
  color: var(--lx-text-placeholder);
}
.field-input:hover {
  border-color: var(--lx-border-strong);
}
.field-input:focus {
  border-color: var(--lx-green);
  box-shadow: 0 0 0 3px var(--lx-green-glow-soft);
}
.error {
  margin: 0;
  font-size: var(--lx-text-sm);
  color: var(--lx-danger);
}
.submit {
  margin-top: var(--lx-space-1);
  padding: var(--lx-space-3);
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-medium);
  color: var(--lx-bg-surface); /* 主绿上的白字（对比度过 WCAG AA，见 tokens.css） */
  background: var(--lx-green);
  border: none;
  border-radius: var(--lx-radius-base);
  cursor: pointer;
  transition: background var(--lx-duration-fast) var(--lx-ease-out);
}
.submit:hover:not(:disabled) {
  background: var(--lx-green-light-3);
}
.submit:active:not(:disabled) {
  transform: translateY(1px);
}
.submit:disabled {
  opacity: 0.6;
  cursor: default;
}
.demo-hint {
  margin: var(--lx-space-4) 0 0;
  font-size: var(--lx-text-xs);
  letter-spacing: 0.06em;
  color: var(--lx-text-placeholder);
}

@media (max-width: 767px) {
  .login-card {
    padding: var(--lx-space-5);
  }
}
</style>

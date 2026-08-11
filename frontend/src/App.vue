<script setup>
import { ref } from 'vue'
import axios from 'axios'

// 阶段 0 验收页：点击按钮调用 GET /api/ping，显示 pong 即前后端链路打通
const result = ref('')
const loading = ref(false)

async function ping() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/ping')
    result.value = data.msg
  } catch (e) {
    result.value = '请求失败：' + e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="page">
    <h1>LabX</h1>
    <p>阶段 0 验收：点击按钮，显示 pong 即前后端链路打通</p>
    <button :disabled="loading" @click="ping">
      {{ loading ? '请求中…' : 'Ping 后端' }}
    </button>
    <p v-if="result" class="result">{{ result }}</p>
  </main>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding-top: 15vh;
}
button {
  font-size: 18px;
  padding: 10px 28px;
  border-radius: 8px;
  border: none;
  background: #42b883;
  color: #fff;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
  cursor: default;
}
.result {
  font-size: 24px;
  font-weight: bold;
  color: #42b883;
}
</style>

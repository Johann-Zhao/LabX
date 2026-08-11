<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { lastBorrowResult } from '../store'

const router = useRouter()

const hasResult = computed(() => !!lastBorrowResult.record_id)

// 应还时间只保留日期部分，展示更友好
const dueText = computed(() => (lastBorrowResult.due_at || '').slice(0, 10))
</script>

<template>
  <div class="page">
    <template v-if="hasResult">
      <el-result icon="success" title="借用成功" :sub-title="`记录号 ${lastBorrowResult.record_id}`">
        <template #extra>
          <p class="line">物料：{{ lastBorrowResult.material_name }}（{{ lastBorrowResult.material_id }}）</p>
          <p class="line">请在 <b>{{ dueText }}</b> 前归还</p>

          <!-- 借用触发的知识卡片：三要点 + "查看全部"深入入口（保姆级教程） -->
          <el-card v-if="lastBorrowResult.knowledge_card" class="kcard" shadow="never">
            <template #header>{{ lastBorrowResult.knowledge_card.title }}</template>
            <ol>
              <li v-for="(p, i) in lastBorrowResult.knowledge_card.points" :key="i">{{ p }}</li>
            </ol>
            <el-button
              text
              type="primary"
              @click="router.push(`/cards/${lastBorrowResult.knowledge_card.card_id}`)"
            >
              查看全部教程 →
            </el-button>
          </el-card>

          <el-button type="primary" @click="router.push('/')">再逛逛</el-button>
          <el-button @click="router.push('/records')">我的借用</el-button>
        </template>
      </el-result>
    </template>
    <el-empty v-else description="还没有借用记录，先去挑一件物料吧">
      <el-button type="primary" @click="router.push('/')">去看物料</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.line {
  margin: 4px 0;
  color: #606266;
}
.kcard {
  margin: 12px 0;
  text-align: left;
}
.kcard ol {
  margin: 0;
  padding-left: 20px;
}
.kcard li {
  margin: 4px 0;
}
</style>

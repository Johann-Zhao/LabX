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
      <el-result icon="success" title="借用成功">
        <template #sub-title>
          记录号 <span class="lx-num">{{ lastBorrowResult.record_id }}</span>
        </template>
        <template #extra>
          <p class="line">物料：{{ lastBorrowResult.material_name }}（<span class="lx-num">{{ lastBorrowResult.material_id }}</span>）</p>
          <p class="line">请在 <span class="due lx-num">{{ dueText }}</span> 前归还</p>

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

          <div class="btns">
            <el-button type="primary" @click="router.push('/materials')">再逛逛</el-button>
            <el-button @click="router.push('/records')">我的借用</el-button>
          </div>
        </template>
      </el-result>
    </template>
    <el-empty v-else description="还没有借用记录，先去挑一件物料吧">
      <el-button type="primary" @click="router.push('/materials')">去看物料</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.line {
  margin: var(--lx-space-1) 0;
  color: var(--lx-text-regular);
  font-size: var(--lx-text-base);
}
/* 应还日期：墨色加粗 + 等宽数字，结果页里最该被看见的信息 */
.due {
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
}
/* 知识卡片：细边框（el-card 全局令牌化），内容左对齐 */
.kcard {
  margin: var(--lx-space-4) 0;
  text-align: left;
}
.kcard :deep(.el-card__header) {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
}
.kcard ol {
  margin: 0;
  padding-left: var(--lx-space-5);
}
.kcard li {
  margin: var(--lx-space-1) 0;
  color: var(--lx-text-regular);
  font-size: var(--lx-text-base);
}
.btns {
  margin-top: var(--lx-space-2);
}
</style>

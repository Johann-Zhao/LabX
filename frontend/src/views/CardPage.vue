<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { fetchCard } from '../api'

const route = useRoute()
const router = useRouter()
const card = ref(null)
const loading = ref(true)

const TYPE_TEXT = {
  manual: '说明书要点',
  quickstart: '三分钟上手',
  common_errors: '常见错误',
  tip: '社区经验',
}

// 卡片正文是团队成员维护的 markdown（deta/cards/），用 marked 渲染
const contentHtml = computed(() => (card.value?.content ? marked.parse(card.value.content) : ''))

onMounted(async () => {
  const res = await fetchCard(route.params.id)
  loading.value = false
  if (res.code === 0) {
    card.value = res.data
  } else {
    ElMessage.error(res.msg)
    router.replace('/')
  }
})
</script>

<template>
  <div v-loading="loading">
    <template v-if="card">
      <el-card shadow="never">
        <div class="head">
          <span class="title">{{ card.title }}</span>
          <el-tag size="small" type="success" class="type-tag">{{ TYPE_TEXT[card.card_type] || card.card_type }}</el-tag>
        </div>
        <div class="meta" @click="router.push(`/materials/${card.material_id}`)">
          所属物料：<span class="lx-num">{{ card.material_id }}</span> →
        </div>

        <ol v-if="card.points?.length" class="points">
          <li v-for="(p, i) in card.points" :key="i">{{ p }}</li>
        </ol>

        <div class="content" v-html="contentHtml" />

        <div v-if="card.source" class="source">
          资料来源：<a :href="card.source.split(/[,，\s]/)[0]" target="_blank" rel="noopener">{{ card.source }}</a>
        </div>
      </el-card>
      <el-button class="back" @click="router.back()">返回</el-button>
    </template>
  </div>
</template>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--lx-space-2);
}
.type-tag {
  flex-shrink: 0;
}
.title {
  font-size: var(--lx-text-lg);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
/* 所属物料：链接语义，主绿 + hover 下划线 */
.meta {
  display: inline-block;
  color: var(--lx-green);
  font-size: var(--lx-text-xs);
  margin-top: var(--lx-space-1);
  cursor: pointer;
}
.meta:hover {
  text-decoration: underline;
}
/* 三要点：浅绿底区块，与正文拉开层级 */
.points {
  background: var(--lx-green-light-9);
  border-radius: var(--lx-radius-md);
  padding: var(--lx-space-3) var(--lx-space-3) var(--lx-space-3) var(--lx-space-6);
  margin: var(--lx-space-3) 0;
}
.points li {
  margin: var(--lx-space-1) 0;
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
}
/* markdown 正文：标题落字阶，表格/代码走细边框 + 浅底 */
.content {
  font-size: var(--lx-text-base);
  line-height: var(--lx-leading);
  color: var(--lx-text-regular);
}
.content :deep(h2) {
  font-size: var(--lx-text-lg);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  margin: var(--lx-space-4) 0 var(--lx-space-2);
}
.content :deep(h3) {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  margin: var(--lx-space-3) 0 var(--lx-space-1);
}
.content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: var(--lx-space-2) 0;
  font-size: var(--lx-text-sm);
}
.content :deep(th),
.content :deep(td) {
  border: 1px solid var(--lx-border-light);
  padding: var(--lx-space-1) var(--lx-space-2);
  text-align: left;
}
.content :deep(th) {
  background: var(--lx-bg-subtle);
}
.content :deep(pre) {
  background: var(--lx-bg-subtle);
  border: 1px solid var(--lx-border-light);
  color: var(--lx-text-regular);
  padding: var(--lx-space-3);
  border-radius: var(--lx-radius-md);
  overflow-x: auto;
  font-size: var(--lx-text-xs);
}
.content :deep(code) {
  font-family: var(--lx-font-mono);
}
.content :deep(p code),
.content :deep(li code),
.content :deep(td code) {
  background: var(--lx-bg-subtle);
  color: var(--lx-text-primary);
  padding: 0 var(--lx-space-1);
  border-radius: var(--lx-radius-sm);
}
.source {
  margin-top: var(--lx-space-4);
  padding-top: var(--lx-space-3);
  border-top: 1px dashed var(--lx-border);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  word-break: break-all;
}
.source a {
  color: var(--lx-green);
}
.back {
  width: 100%;
  margin-top: var(--lx-space-3);
}
</style>

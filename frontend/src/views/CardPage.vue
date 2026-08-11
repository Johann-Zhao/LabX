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
          <el-tag size="small" type="success">{{ TYPE_TEXT[card.card_type] || card.card_type }}</el-tag>
        </div>
        <div class="meta" @click="router.push(`/materials/${card.material_id}`)">
          所属物料：{{ card.material_id }} →
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
  align-items: center;
  gap: 8px;
}
.title {
  font-size: 18px;
  font-weight: bold;
}
.meta {
  color: #42b883;
  font-size: 12px;
  margin-top: 4px;
  cursor: pointer;
}
.points {
  background: #f0f9eb;
  border-radius: 8px;
  padding: 10px 10px 10px 28px;
  margin: 12px 0;
}
.points li {
  margin: 4px 0;
  font-size: 14px;
}
.content {
  font-size: 14px;
  line-height: 1.8;
}
.content :deep(h2) {
  font-size: 16px;
  margin: 16px 0 8px;
}
.content :deep(h3) {
  font-size: 15px;
  margin: 14px 0 6px;
}
.content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 13px;
}
.content :deep(th),
.content :deep(td) {
  border: 1px solid #ebeef5;
  padding: 6px 8px;
  text-align: left;
}
.content :deep(th) {
  background: #f5f7fa;
}
.content :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
}
.content :deep(code) {
  font-family: Consolas, Monaco, monospace;
}
.content :deep(p code),
.content :deep(li code),
.content :deep(td code) {
  background: #f5f7fa;
  color: #c7254e;
  padding: 1px 4px;
  border-radius: 4px;
}
.source {
  margin-top: 16px;
  padding-top: 10px;
  border-top: 1px dashed #ebeef5;
  font-size: 12px;
  color: #909399;
  word-break: break-all;
}
.source a {
  color: #42b883;
}
.back {
  width: 100%;
  margin-top: 12px;
}
</style>

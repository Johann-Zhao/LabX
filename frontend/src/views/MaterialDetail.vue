<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { borrowMaterial, fetchMaterial } from '../api'
import { currentUser, lastBorrowResult } from '../store'

const route = useRoute()
const router = useRouter()
const material = ref(null)
const loading = ref(true)
const borrowing = ref(false)

const LEVEL_TYPE = { basic: 'success', advanced: 'warning', professional: 'danger' }
const LEVEL_TEXT = { basic: '基础级', advanced: '进阶级', professional: '专业级' }

onMounted(async () => {
  const res = await fetchMaterial(route.params.id)
  loading.value = false
  if (res.code === 0) {
    material.value = res.data
  } else {
    ElMessage.error(res.msg)
    router.replace('/')
  }
})

async function onBorrow() {
  try {
    await ElMessageBox.confirm(
      `确认借用「${material.value.name}」？借用记录将与你的账号绑定。`,
      '确认借用',
      { confirmButtonText: '确认借用', cancelButtonText: '再想想', type: 'info' }
    )
  } catch {
    return // 用户点了取消
  }
  borrowing.value = true
  try {
    const res = await borrowMaterial(currentUser.id, material.value.material_id)
    if (res.code === 0) {
      Object.assign(lastBorrowResult, {
        record_id: res.data.record_id,
        material_id: material.value.material_id,
        material_name: material.value.name,
        due_at: res.data.due_at,
        knowledge_card: res.data.knowledge_card,
      })
      router.push('/borrow/result')
    } else if (res.code === 1005) {
      ElMessageBox.confirm(res.msg, '提示', {
        confirmButtonText: '去归还',
        cancelButtonText: '取消',
        type: 'warning',
      }).then(() => router.push('/records')).catch(() => {})
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    borrowing.value = false
  }
}
</script>

<template>
  <div v-loading="loading">
    <template v-if="material">
      <el-card>
        <div class="row">
          <span class="name">{{ material.name }}</span>
          <el-tag :type="LEVEL_TYPE[material.access_level]">
            {{ LEVEL_TEXT[material.access_level] || material.access_level }}
          </el-tag>
        </div>
        <div class="meta">{{ material.material_id }} · {{ material.model || '无型号' }} · {{ material.category }}</div>
        <p class="desc">{{ material.description }}</p>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="存放位置">{{ material.location }}</el-descriptions-item>
          <el-descriptions-item label="库存">
            可借 {{ material.available_quantity }} / 共 {{ material.total_quantity }}
          </el-descriptions-item>
          <el-descriptions-item label="社区经验">{{ material.tips_count }} 条</el-descriptions-item>
        </el-descriptions>

        <!-- 知识卡片（数字分身）由阶段 2 接入，当前后端返回空列表 -->
        <div v-if="material.knowledge_cards?.length" class="cards">
          <div v-for="c in material.knowledge_cards" :key="c.card_id" class="kcard">
            {{ c.title }}
          </div>
        </div>

        <el-button
          type="primary"
          size="large"
          class="borrow-btn"
          :disabled="material.available_quantity === 0"
          :loading="borrowing"
          @click="onBorrow"
        >
          {{ material.available_quantity === 0 ? '暂时缺货' : '确认借用' }}
        </el-button>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-size: 20px;
  font-weight: bold;
}
.meta {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.desc {
  color: #606266;
  margin: 12px 0;
}
.cards {
  margin-top: 12px;
}
.kcard {
  padding: 8px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 6px;
}
.borrow-btn {
  width: 100%;
  margin-top: 16px;
}
</style>

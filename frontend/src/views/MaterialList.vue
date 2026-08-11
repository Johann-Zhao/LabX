<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchMaterials } from '../api'

const router = useRouter()
const keyword = ref('')
const materials = ref([])
const loading = ref(false)

// 借阅等级标签颜色
const LEVEL_TYPE = { basic: 'success', advanced: 'warning', professional: 'danger' }
const LEVEL_TEXT = { basic: '基础级', advanced: '进阶级', professional: '专业级' }

async function load() {
  loading.value = true
  try {
    const res = await fetchMaterials(keyword.value.trim())
    if (res.code === 0) {
      materials.value = res.data
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <el-input
      v-model="keyword"
      placeholder="搜索物料名称或型号，如 DHT22"
      clearable
      size="large"
      @keyup.enter="load"
      @clear="load"
    >
      <template #append>
        <el-button @click="load">搜索</el-button>
      </template>
    </el-input>

    <div v-loading="loading" class="list">
      <el-card
        v-for="m in materials"
        :key="m.material_id"
        class="card"
        shadow="hover"
        @click="router.push(`/materials/${m.material_id}`)"
      >
        <div class="row">
          <span class="name">{{ m.name }}</span>
          <el-tag :type="LEVEL_TYPE[m.access_level]" size="small">
            {{ LEVEL_TEXT[m.access_level] || m.access_level }}
          </el-tag>
        </div>
        <div class="meta">{{ m.material_id }} · {{ m.model || '无型号' }} · {{ m.category }}</div>
        <div class="desc">{{ m.description }}</div>
        <div class="row bottom">
          <span class="location">{{ m.location }}</span>
          <span :class="['stock', m.available_quantity === 0 ? 'empty' : '']">
            可借 {{ m.available_quantity }} / 共 {{ m.total_quantity }}
          </span>
        </div>
      </el-card>
      <el-empty v-if="!loading && materials.length === 0" description="没有找到匹配的物料" />
    </div>
  </div>
</template>

<style scoped>
.list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.card {
  cursor: pointer;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-size: 16px;
  font-weight: bold;
}
.meta {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.desc {
  color: #606266;
  font-size: 14px;
  margin-top: 6px;
}
.bottom {
  margin-top: 8px;
  font-size: 13px;
}
.location {
  color: #909399;
}
.stock {
  color: #42b883;
  font-weight: bold;
}
.stock.empty {
  color: #f56c6c;
}
</style>

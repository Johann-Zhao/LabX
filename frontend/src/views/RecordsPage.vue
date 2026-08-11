<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchRecords, returnMaterial } from '../api'
import { currentUser } from '../store'

const records = ref([])
const loading = ref(false)
const returningId = ref('')

const STATUS_META = {
  active: { text: '借用中', type: 'primary' },
  overdue: { text: '已逾期', type: 'danger' },
  returned: { text: '已归还', type: 'info' },
  pending: { text: '待审批', type: 'warning' },
}

function fmt(iso) {
  // ISO 字符串 → 'MM-DD HH:mm'，空值显示 —
  return iso ? iso.slice(5, 16).replace('T', ' ') : '—'
}

async function load() {
  loading.value = true
  try {
    const res = await fetchRecords(currentUser.id)
    if (res.code === 0) {
      records.value = res.data
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    loading.value = false
  }
}

async function onReturn(record) {
  try {
    await ElMessageBox.confirm(`确认归还「${record.material_name}」？`, '确认归还', {
      confirmButtonText: '确认归还',
      cancelButtonText: '取消',
      type: 'info',
    })
  } catch {
    return
  }
  returningId.value = record.record_id
  try {
    const res = await returnMaterial(record.record_id)
    if (res.code === 0) {
      ElMessage.success('归还成功')
      // 阶段 3：此处弹出 AI 预填的心得草稿（res.data.experience_draft）
      await load()
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    returningId.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="list">
    <el-card v-for="r in records" :key="r.record_id" class="card" shadow="never">
      <div class="row">
        <span class="name">{{ r.material_name }}</span>
        <el-tag :type="STATUS_META[r.status]?.type || 'info'" size="small">
          {{ STATUS_META[r.status]?.text || r.status }}
        </el-tag>
      </div>
      <div class="meta">{{ r.record_id }} · {{ r.material_id }}</div>
      <div class="times">
        <span>借出 {{ fmt(r.borrowed_at) }}</span>
        <span>应还 {{ fmt(r.due_at) }}</span>
        <span v-if="r.returned_at">实还 {{ fmt(r.returned_at) }}</span>
      </div>
      <el-button
        v-if="r.status === 'active' || r.status === 'overdue'"
        type="primary"
        plain
        size="small"
        class="btn"
        :loading="returningId === r.record_id"
        @click="onReturn(r)"
      >
        归还
      </el-button>
    </el-card>
    <el-empty v-if="!loading && records.length === 0" description="还没有借用记录">
      <el-button type="primary" @click="$router.push('/')">去借一件</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
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
.times {
  display: flex;
  gap: 12px;
  color: #606266;
  font-size: 13px;
  margin-top: 8px;
}
.btn {
  margin-top: 10px;
}
</style>

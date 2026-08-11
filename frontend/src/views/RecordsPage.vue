<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchRecords, returnMaterial, submitExperience } from '../api'
import { currentUser } from '../store'

const records = ref([])
const loading = ref(false)
const returningId = ref('')

// 归还心得弹窗（AI 预填草稿，改一句话即可发布——把"创作"降为"改错"）
const expDialog = ref(false)
const expDraft = ref('')
const expRecord = ref(null)
const publishing = ref(false)

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
      await load()
      // AI 预填心得草稿：弹出供学生修改或确认（非强制）
      if (res.data.experience_draft) {
        expRecord.value = record
        expDraft.value = res.data.experience_draft
        expDialog.value = true
      }
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    returningId.value = ''
  }
}

async function publishExperience() {
  if (!expDraft.value.trim() || publishing.value) return
  publishing.value = true
  try {
    const res = await submitExperience({
      materialId: expRecord.value.material_id,
      userId: currentUser.id,
      content: expDraft.value.trim(),
      recordId: expRecord.value.record_id,
    })
    if (res.code === 0) {
      ElMessage.success('经验已分享，下一个借它的同学会看到')
      expDialog.value = false
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    publishing.value = false
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

    <!-- 归还心得：AI 预填草稿，学生改一句话即可发布（非强制） -->
    <el-dialog v-model="expDialog" title="用得顺利吗？" width="90%">
      <p class="exp-tip">AI 根据你的借用情况预填了心得草稿，改一句话就能分享给下一个同学：</p>
      <el-input v-model="expDraft" type="textarea" :rows="4" />
      <template #footer>
        <el-button @click="expDialog = false">不了，谢谢</el-button>
        <el-button type="primary" :loading="publishing" @click="publishExperience">发布心得</el-button>
      </template>
    </el-dialog>
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
.exp-tip {
  color: #606266;
  font-size: 13px;
  margin: 0 0 8px;
}
</style>

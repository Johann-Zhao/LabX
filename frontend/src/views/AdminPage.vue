<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchRecords, reviewBorrow } from '../api'

const records = ref([])
const loading = ref(false)
const reviewingId = ref('') // 正在审核的记录号，按钮转圈防重复点击

// 五态展示文案（与 RecordsPage 一致）
const STATUS_META = {
  active: { text: '借用中', type: 'primary' },
  overdue: { text: '已逾期', type: 'danger' },
  returned: { text: '已归还', type: 'info' },
  pending: { text: '审核中', type: 'warning' },
  rejected: { text: '已驳回', type: 'info' },
}

function fmt(iso) {
  // ISO 字符串 → 'MM-DD HH:mm'，空值显示 —
  return iso ? iso.slice(5, 16).replace('T', ' ') : '—'
}

// 申请借期天数 = 应还时间 - 申请时间（审核通过前 borrowed_at 即申请时间，算法同后端 services.py）
function borrowDays(r) {
  return Math.round((new Date(r.due_at) - new Date(r.borrowed_at)) / 86400000)
}

const pendingRecords = computed(() => records.value.filter((r) => r.status === 'pending'))

// 借用中：active + overdue，按物料名排序（中文按拼音）
const activeRecords = computed(() =>
  records.value
    .filter((r) => r.status === 'active' || r.status === 'overdue')
    .sort((a, b) => a.material_name.localeCompare(b.material_name, 'zh'))
)

async function load() {
  loading.value = true
  try {
    const res = await fetchRecords() // 不带 user_id，返回全部记录（管理员视角）
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

async function onReview(r, approve) {
  if (!approve) {
    // 驳回是终态操作，二次确认防误点
    try {
      await ElMessageBox.confirm(`确认驳回「${r.material_name}」的借用申请？`, '确认驳回', {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }
  }
  reviewingId.value = r.record_id
  try {
    const res = await reviewBorrow(r.record_id, approve)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      await load()
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    reviewingId.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-tabs>
      <!-- 待审核：>30 天的借用申请，通过 / 驳回 -->
      <el-tab-pane>
        <template #label>
          <el-badge
            :value="pendingRecords.length"
            :show-zero="false"
            type="danger"
          >
            待审核
          </el-badge>
        </template>
        <div class="list">
          <el-card v-for="r in pendingRecords" :key="r.record_id" class="card" shadow="never">
            <div class="row">
              <span class="name">
                {{ r.material_name }}<template v-if="r.quantity > 1"> ×{{ r.quantity }}</template>
              </span>
              <div class="actions">
                <el-button
                  type="success"
                  size="small"
                  :loading="reviewingId === r.record_id"
                  @click="onReview(r, true)"
                >
                  通过
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  plain
                  :loading="reviewingId === r.record_id"
                  @click="onReview(r, false)"
                >
                  驳回
                </el-button>
              </div>
            </div>
            <div class="meta">{{ r.user_name }}（{{ r.user_id }}）· {{ r.record_id }}</div>
            <div class="times">
              <span>申请于 {{ fmt(r.borrowed_at) }}</span>
              <span>借期 {{ borrowDays(r) }} 天</span>
            </div>
            <div v-if="r.review_reason" class="reason">申请理由：{{ r.review_reason }}</div>
          </el-card>
          <el-empty v-if="!loading && pendingRecords.length === 0" description="没有待审核的申请" />
        </div>
      </el-tab-pane>

      <!-- 借用中：当前谁手里有什么物料，按物料名排序（列宽按 620px 内容区调瘦） -->
      <el-tab-pane label="借用中">
        <p class="hint">物料当前持有人一览</p>
        <el-table :data="activeRecords" stripe>
          <el-table-column label="物料" min-width="150">
            <template #default="{ row }">
              {{ row.material_name }}<template v-if="row.quantity > 1"> ×{{ row.quantity }}</template>
            </template>
          </el-table-column>
          <el-table-column prop="user_name" label="在谁手里" width="80" />
          <el-table-column label="借出" width="115">
            <template #default="{ row }">{{ fmt(row.borrowed_at) }}</template>
          </el-table-column>
          <el-table-column label="应还" width="115">
            <template #default="{ row }">{{ fmt(row.due_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="76">
            <template #default="{ row }">
              <el-tag :type="STATUS_META[row.status].type" size="small">
                {{ STATUS_META[row.status].text }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 全部流水：按借出时间倒序（后端已排好）；卡片式，窄屏自适应 -->
      <el-tab-pane label="全部流水">
        <div class="list">
          <el-card v-for="r in records" :key="r.record_id" class="card" shadow="never">
            <div class="row">
              <span class="name">
                {{ r.material_name }}<template v-if="r.quantity > 1"> ×{{ r.quantity }}</template>
              </span>
              <el-tag :type="STATUS_META[r.status]?.type || 'info'" size="small">
                {{ STATUS_META[r.status]?.text || r.status }}
              </el-tag>
            </div>
            <div class="meta">{{ r.user_name }}（{{ r.user_id }}）· {{ r.record_id }}</div>
            <div class="times">
              <span>借出 {{ fmt(r.borrowed_at) }}</span>
              <span>应还 {{ fmt(r.due_at) }}</span>
              <span v-if="r.returned_at">实还 {{ fmt(r.returned_at) }}</span>
            </div>
          </el-card>
          <el-empty v-if="!loading && records.length === 0" description="还没有任何借用记录" />
        </div>
      </el-tab-pane>
    </el-tabs>
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
.actions {
  display: flex;
  gap: 8px;
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
.reason {
  color: #909399;
  font-size: 12px;
  margin-top: 6px;
}
.hint {
  color: #909399;
  font-size: 13px;
  margin: 0 0 8px;
}
</style>

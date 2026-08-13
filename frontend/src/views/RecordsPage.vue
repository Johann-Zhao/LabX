<script setup>
import { computed, onMounted, ref } from 'vue'
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
  pending: { text: '审核中', type: 'warning' },
  rejected: { text: '已驳回', type: 'info' },
}

// 记录按状态分组：待归还（含逾期）→ 审核中 → 历史记录；组内沿用接口返回顺序
const GROUP_DEFS = [
  { key: 'borrowing', title: '待归还', statuses: ['active', 'overdue'] },
  { key: 'pending', title: '审核中', statuses: ['pending'] },
  { key: 'history', title: '历史记录', statuses: ['returned', 'rejected'] },
]
// 状态筛选：默认全部，点胶囊只看对应分组
const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'borrowing', label: '待归还' },
  { key: 'pending', label: '审核中' },
  { key: 'history', label: '历史记录' },
]
const filter = ref('all')
const grouped = computed(() => {
  const groups = GROUP_DEFS.map((g) => ({
    ...g,
    items: records.value.filter((r) => g.statuses.includes(r.status)),
  })).filter((g) => g.items.length > 0)
  return filter.value === 'all' ? groups : groups.filter((g) => g.key === filter.value)
})

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
  <div v-loading="loading">
    <!-- 状态筛选胶囊：默认全部，点选只看对应分组 -->
    <div class="filter-chips">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        type="button"
        class="fchip lx-num"
        :class="{ active: filter === f.key }"
        @click="filter = f.key"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- 按状态分组的记录卡片：待归还 → 审核中 → 历史记录 -->
    <section v-for="g in grouped" :key="g.key" class="group">
      <div class="group-title">
        {{ g.title }} <span class="group-count lx-num">{{ g.items.length }}</span>
      </div>
      <div class="cards">
        <article v-for="r in g.items" :key="r.record_id" class="card">
          <div class="row">
            <span class="name">
              {{ r.material_name }}<template v-if="r.quantity > 1"> <span class="lx-num">×{{ r.quantity }}</span></template>
            </span>
            <el-tag :type="STATUS_META[r.status]?.type || 'info'" size="small" class="status-tag">
              {{ STATUS_META[r.status]?.text || r.status }}
            </el-tag>
          </div>
          <div class="meta lx-num">{{ r.record_id }} · {{ r.material_id }}</div>
          <!-- 时间行：等宽数字；逾期的应还时间用危险色 -->
          <div class="times">
            <span class="time">借出 <span class="lx-num">{{ fmt(r.borrowed_at) }}</span></span>
            <span :class="['time', { danger: r.status === 'overdue' }]">应还 <span class="lx-num">{{ fmt(r.due_at) }}</span></span>
            <span v-if="r.returned_at" class="time">实还 <span class="lx-num">{{ fmt(r.returned_at) }}</span></span>
          </div>
          <div v-if="r.review_reason" class="reason">申请理由：{{ r.review_reason }}</div>
          <div v-if="r.status === 'active' || r.status === 'overdue'" class="foot">
            <el-button
              type="primary"
              plain
              size="small"
              :loading="returningId === r.record_id"
              @click="onReturn(r)"
            >
              归还
            </el-button>
          </div>
        </article>
      </div>
    </section>

    <el-empty v-if="!loading && records.length === 0" description="还没有借用记录">
      <el-button type="primary" @click="$router.push('/materials')">去借一件</el-button>
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
/* 筛选胶囊：与物料页同一套仪器分段语言 */
.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--lx-space-2);
  margin-bottom: var(--lx-space-4);
}
.fchip {
  padding: 2px var(--lx-space-3);
  font-size: var(--lx-text-xs);
  letter-spacing: 0.04em;
  color: var(--lx-text-secondary);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-pill);
  cursor: pointer;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    background-color var(--lx-duration-fast) var(--lx-ease-out),
    border-color var(--lx-duration-fast) var(--lx-ease-out);
}
.fchip:hover {
  color: var(--lx-text-primary);
  border-color: var(--lx-border-strong);
}
.fchip.active {
  color: var(--lx-green);
  background: var(--lx-green-light-9);
  border-color: var(--lx-green-light-7);
  font-weight: var(--lx-font-medium);
}
.group {
  margin-bottom: var(--lx-space-5);
}
.group-title {
  font-size: var(--lx-text-sm);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-secondary);
  margin-bottom: var(--lx-space-2);
}
.group-count {
  color: var(--lx-text-placeholder);
  font-weight: var(--lx-font-regular);
  margin-left: var(--lx-space-1);
}
.cards {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}

/* 记录卡片：细边框分组，不用阴影 */
.card {
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  padding: var(--lx-space-3) var(--lx-space-4);
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--lx-space-2);
}
.status-tag {
  flex-shrink: 0;
}
.name {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
.meta {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
  margin-top: var(--lx-space-1);
}
/* 时间行：窄屏自动换行；逾期应还整行染危险色 */
.times {
  display: flex;
  flex-wrap: wrap;
  gap: var(--lx-space-1) var(--lx-space-4);
  color: var(--lx-text-regular);
  font-size: var(--lx-text-sm);
  margin-top: var(--lx-space-2);
}
.time.danger {
  color: var(--lx-danger);
  font-weight: var(--lx-font-medium);
}
/* 申请理由：浅色内嵌条，与正文拉开层级 */
.reason {
  background: var(--lx-bg-subtle);
  border-radius: var(--lx-radius-sm);
  padding: var(--lx-space-2) var(--lx-space-3);
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
  margin-top: var(--lx-space-2);
}
.foot {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--lx-space-3);
}
.exp-tip {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-sm);
  margin: 0 0 var(--lx-space-2);
}
</style>

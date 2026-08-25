<script setup>
// 管理台独立布局：左侧功能栏 + 右侧内容区（/admin 下 App.vue 不渲染学生端外壳）
// 五个区块：审核申请 / 当前在借 / 全部流水（原三面板逻辑原样保留）/ 批量借出 / 录入物料
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  batchBorrow,
  createMaterial,
  fetchMaterials,
  fetchRecords,
  fetchUploads,
  fetchUsers,
  reviewBorrow,
  reviewUpload,
} from '../api'
import { logout } from '../store'

const router = useRouter()

// 退出登录：清登录态回 /login（路由守卫会兜住后续所有页面访问）
function onLogout() {
  logout()
  router.push('/login')
}

const currentView = ref('pending') // pending / active / records / batch / create / uploads

// ---------- 资料审核 ----------

const uploads = ref([])
const uploadsLoading = ref(false)
const uploadReviewingId = ref('')
const uploadRejectNote = ref('')
const uploadRejectDialog = ref(false)
const uploadRejectTarget = ref(null)

async function loadUploads() {
  uploadsLoading.value = true
  try {
    const res = await fetchUploads('', 'pending')
    if (res.code === 0) {
      uploads.value = res.data
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    uploadsLoading.value = false
  }
}

async function onUploadReview(u, approve) {
  if (!approve) {
    uploadRejectTarget.value = u
    uploadRejectNote.value = ''
    uploadRejectDialog.value = true
    return
  }
  uploadReviewingId.value = u.upload_id
  try {
    const res = await reviewUpload(u.upload_id, true)
    if (res.code === 0) {
      ElMessage.success(res.msg)
      await loadUploads()
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    uploadReviewingId.value = ''
  }
}

async function onUploadRejectConfirm() {
  const u = uploadRejectTarget.value
  if (!u) return
  uploadReviewingId.value = u.upload_id
  try {
    const res = await reviewUpload(u.upload_id, false, uploadRejectNote.value.trim())
    if (res.code === 0) {
      ElMessage.success('已驳回')
      uploadRejectDialog.value = false
      await loadUploads()
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    uploadReviewingId.value = ''
  }
}

function fmtSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// ---------- 审核申请 / 当前在借 / 全部流水（原 AdminPage 逻辑） ----------

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

// ---------- 批量借出（API.md 第 3.2 节） ----------

const users = ref([]) // 借用人候选
const materials = ref([]) // 全量物料（可借 > 0 的行才可选）
const batchTableRef = ref() // 物料选择表 ref，提交后清空选择
const batchKeyword = ref('') // 表格关键字筛选（只影响显示，不影响已勾选）
// 批量借出表格：按关键字即时过滤（名称/型号/分类），物料多了不用滚半天
const batchMaterials = computed(() => {
  const kw = batchKeyword.value.trim().toLowerCase()
  if (!kw) return materials.value
  return materials.value.filter((m) =>
    [m.name, m.model, m.category, m.material_id].some((v) => String(v || '').toLowerCase().includes(kw))
  )
})
const selectedRows = ref([]) // 当前勾选的行（selection-change 回调）
const qtyMap = ref({}) // material_id → 借几件（默认 1）
const batchUser = ref('')
const batchDays = ref('30') // '7' | '14' | '30' | 'more'
const batchCustomDays = ref(60)
const batchReason = ref('')
const batchResults = ref([]) // 逐行结果（成功绿 / 失败红）
const submitting = ref(false)

const selectedSet = computed(() => new Set(selectedRows.value.map((r) => r.material_id)))
// 已选件数 = 各行数量之和（按钮文案用）
const selectedTotal = computed(() =>
  selectedRows.value.reduce((s, r) => s + (qtyMap.value[r.material_id] || 1), 0)
)

function onSelectionChange(rows) {
  selectedRows.value = rows
  for (const r of rows) {
    if (!(r.material_id in qtyMap.value)) qtyMap.value[r.material_id] = 1 // 新勾选默认 1 件
  }
}

async function refreshMaterials() {
  const res = await fetchMaterials()
  if (res.code === 0) materials.value = res.data
}

async function onBatchSubmit() {
  if (!batchUser.value) {
    ElMessage.warning('请先选择借用人')
    return
  }
  const days = batchDays.value === 'more' ? batchCustomDays.value : Number(batchDays.value)
  if (batchDays.value === 'more' && !batchReason.value.trim()) {
    ElMessage.warning('超过 30 天需填写申请理由，提交后转人工审核')
    return
  }
  submitting.value = true
  batchResults.value = []
  try {
    const items = selectedRows.value.map((r) => ({
      material_id: r.material_id,
      quantity: qtyMap.value[r.material_id] || 1,
    }))
    const res = await batchBorrow(batchUser.value, items, days, batchReason.value.trim())
    if (res.code === 0) {
      batchResults.value = res.data.results
      const failed = res.data.results.filter((x) => x.code !== 0).length
      if (failed > 0) {
        ElMessage.warning(`借出完成：${res.data.results.length - failed} 件成功，${failed} 件失败`)
      } else {
        ElMessage.success(`借出成功 ${res.data.results.length} 件`)
      }
      await refreshMaterials() // 重新拉物料列表刷新库存
      batchTableRef.value?.clearSelection()
      selectedRows.value = []
    } else {
      ElMessage.warning(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    submitting.value = false
  }
}

// ---------- 录入物料（API.md 第 1.1 节） ----------

const CATEGORIES = ['开发板', '传感器', '驱动模块', '工具', '耗材', '设备']
const ACCESS_LEVELS = [
  { value: 'basic', label: '基础级（直接借）' },
  { value: 'advanced', label: '进阶级（首次需安全确认）' },
  { value: 'professional', label: '专业级（需教师审批）' },
]

const form = reactive({
  name: '',
  category: '',
  model: '',
  location: '201室',
  total_quantity: 1,
  access_level: 'basic',
  description: '',
})
const creating = ref(false)

async function onCreate() {
  creating.value = true
  try {
    const res = await createMaterial({ ...form })
    if (res.code === 0) {
      ElMessage.success(`已录入，编号 ${res.data.material_id}`)
      form.name = ''
      form.category = ''
      form.model = ''
      form.location = '201室'
      form.total_quantity = 1
      form.access_level = 'basic'
      form.description = ''
      refreshMaterials() // 新物料立刻出现在批量借出候选里
    } else {
      ElMessage.warning(res.msg) // 1007：分类非法 / 名称重复
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    creating.value = false
  }
}

// ---------- 初始化 ----------

watch(currentView, (v) => {
  if (v === 'batch') refreshMaterials() // 进批量借出时刷新库存，避免用过期的可借数
  if (v === 'uploads') loadUploads() // 进资料审核时刷新列表
})

onMounted(async () => {
  load() // 借用流水（审核 / 在借 / 流水三面板共用）
  const [u, m] = await Promise.all([fetchUsers(), fetchMaterials()])
  if (u.code === 0) users.value = u.data
  if (m.code === 0) materials.value = m.data
})
</script>

<template>
  <div class="admin">
    <!-- 左侧功能栏 -->
    <aside class="sidebar">
      <div class="side-title">管理台</div>
      <div class="menu">
        <div
          class="item"
          :class="{ active: currentView === 'pending' }"
          @click="currentView = 'pending'"
        >
          <span class="side-main">
            <span class="side-idx lx-num">01</span>
            <span class="side-label">审核申请</span>
          </span>
          <el-badge
            :value="pendingRecords.length"
            :show-zero="false"
            type="danger"
            class="side-badge"
          />
        </div>
        <div class="item" :class="{ active: currentView === 'active' }" @click="currentView = 'active'">
          <span class="side-main">
            <span class="side-idx lx-num">02</span>
            <span class="side-label">当前在借</span>
          </span>
        </div>
        <div class="item" :class="{ active: currentView === 'records' }" @click="currentView = 'records'">
          <span class="side-main">
            <span class="side-idx lx-num">03</span>
            <span class="side-label">全部流水</span>
          </span>
        </div>
        <div class="item" :class="{ active: currentView === 'batch' }" @click="currentView = 'batch'">
          <span class="side-main">
            <span class="side-idx lx-num">04</span>
            <span class="side-label">批量借出</span>
          </span>
        </div>
        <div class="item" :class="{ active: currentView === 'create' }" @click="currentView = 'create'">
          <span class="side-main">
            <span class="side-idx lx-num">05</span>
            <span class="side-label">录入物料</span>
          </span>
        </div>
        <div class="item" :class="{ active: currentView === 'uploads' }" @click="currentView = 'uploads'">
          <span class="side-main">
            <span class="side-idx lx-num">06</span>
            <span class="side-label">资料审核</span>
          </span>
          <el-badge
            :value="uploads.length"
            :show-zero="false"
            type="danger"
            class="side-badge"
          />
        </div>
      </div>
      <div class="side-foot">
        <router-link to="/" class="back">← 返回学生端</router-link>
        <button type="button" class="back back-btn" @click="onLogout">退出登录</button>
      </div>
    </aside>

    <!-- 右侧内容区 -->
    <main class="content" v-loading="loading">
      <!-- 待审核：>30 天的借用申请，通过 / 驳回 -->
      <div v-if="currentView === 'pending'" class="list">
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
        <el-empty v-if="!loading && pendingRecords.length === 0" description="没有待审核的申请">
          <span class="empty-hint">借期超过 30 天的申请会流转到这里，通过后自动起算借期。</span>
        </el-empty>
      </div>

      <!-- 当前在借：物料当前持有人一览 -->
      <div v-else-if="currentView === 'active'">
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
      </div>

      <!-- 全部流水：按借出时间倒序（后端已排好）；卡片式 -->
      <div v-else-if="currentView === 'records'" class="list">
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
        <el-empty v-if="!loading && records.length === 0" description="还没有任何借用记录">
          <span class="empty-hint">可以从左侧「批量借出」代学生借出第一件物料。</span>
        </el-empty>
      </div>

      <!-- 批量借出：管理员代借，逐件走借用状态机 -->
      <div v-else-if="currentView === 'batch'" class="batch">
        <div class="form-row">
          <span class="label">借用人</span>
          <el-select v-model="batchUser" filterable placeholder="选择借用人" style="width: 240px">
            <el-option
              v-for="u in users"
              :key="u.user_id"
              :label="`${u.name}（${u.user_id}）`"
              :value="u.user_id"
            />
          </el-select>
        </div>
        <div class="form-row">
          <span class="label">借期</span>
          <el-radio-group v-model="batchDays">
            <el-radio value="7">7 天</el-radio>
            <el-radio value="14">14 天</el-radio>
            <el-radio value="30">30 天</el-radio>
            <el-radio value="more">更久…</el-radio>
          </el-radio-group>
        </div>
        <template v-if="batchDays === 'more'">
          <div class="form-row">
            <span class="label">天数</span>
            <el-input-number v-model="batchCustomDays" :min="31" :max="180" size="small" />
            <span class="inline-hint">最长 180 天</span>
          </div>
          <div class="form-row">
            <span class="label">理由</span>
            <el-input
              v-model="batchReason"
              type="textarea"
              :rows="2"
              placeholder="超过 30 天需填写申请理由，提交后转人工审核"
              class="wide"
            />
          </div>
        </template>

        <div class="table-wrap">
          <el-input
            v-model="batchKeyword"
            placeholder="筛选物料名称 / 型号 / 分类"
            clearable
            size="small"
            class="batch-filter"
          />
          <el-table
            ref="batchTableRef"
            :data="batchMaterials"
            stripe
            @selection-change="onSelectionChange"
          >
            <el-table-column type="selection" width="44" :selectable="(row) => row.available_quantity > 0" />
            <el-table-column prop="name" label="物料" min-width="170" />
            <el-table-column prop="model" label="型号" min-width="130" />
            <el-table-column prop="available_quantity" label="可借" width="64" />
            <el-table-column label="数量" width="150">
              <template #default="{ row }">
                <el-input-number
                  v-model="qtyMap[row.material_id]"
                  :min="1"
                  :max="row.available_quantity"
                  size="small"
                  :disabled="!selectedSet.has(row.material_id)"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="actions">
          <el-button
            type="primary"
            :disabled="selectedRows.length === 0 || !batchUser"
            :loading="submitting"
            @click="onBatchSubmit"
          >
            提交借出（共 {{ selectedTotal }} 件）
          </el-button>
          <el-button @click="batchTableRef?.clearSelection(); selectedRows = []">清空选择</el-button>
        </div>

        <!-- 逐行结果：成功绿色（带记录号）/ 失败红色 -->
        <div v-if="batchResults.length" class="results">
          <div
            v-for="res in batchResults"
            :key="res.material_id || res.msg"
            class="result-line"
            :class="res.code === 0 ? 'ok' : 'fail'"
          >
            <span class="res-name">{{ res.name }}</span>
            <template v-if="res.code === 0">
              {{ res.msg }}<span class="res-id" v-if="res.record_id">{{ res.record_id }}</span>
            </template>
            <template v-else>✗ {{ res.msg }}</template>
          </div>
        </div>
      </div>

      <!-- 录入物料：编号自动生成（开发板 A / 传感器 S / 驱动模块 M / 工具 T / 耗材 H / 设备 E） -->
      <div v-else-if="currentView === 'create'" class="create">
        <div class="form-row">
          <span class="label">名称 *</span>
          <el-input v-model="form.name" placeholder="如：SG90 舵机" class="wide" />
        </div>
        <div class="form-row">
          <span class="label">分类 *</span>
          <el-select v-model="form.category" placeholder="选择分类" style="width: 240px">
            <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
        <div class="form-row">
          <span class="label">型号</span>
          <el-input v-model="form.model" placeholder="如：SG90 9g" class="wide" />
        </div>
        <div class="form-row">
          <span class="label">存放位置</span>
          <el-input v-model="form.location" class="wide" />
        </div>
        <div class="form-row">
          <span class="label">数量</span>
          <el-input-number v-model="form.total_quantity" :min="1" :max="99" />
        </div>
        <div class="form-row">
          <span class="label">借用等级</span>
          <el-select v-model="form.access_level" style="width: 240px">
            <el-option
              v-for="a in ACCESS_LEVELS"
              :key="a.value"
              :label="a.label"
              :value="a.value"
            />
          </el-select>
        </div>
        <div class="form-row">
          <span class="label">用途</span>
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="一句话说明用途"
            class="wide"
          />
        </div>
        <div class="actions">
          <el-button
            type="primary"
            :disabled="!form.name || !form.category"
            :loading="creating"
            @click="onCreate"
          >
            录入物料
          </el-button>
        </div>
      </div>

      <!-- 资料审核：学生上传的资料，通过并入知识库 / 驳回 -->
      <div v-else-if="currentView === 'uploads'" class="list" v-loading="uploadsLoading">
        <el-card v-for="u in uploads" :key="u.upload_id" class="card" shadow="never">
          <div class="row">
            <span class="name">{{ u.filename }}</span>
            <div class="actions">
              <el-button
                type="success"
                size="small"
                :loading="uploadReviewingId === u.upload_id"
                @click="onUploadReview(u, true)"
              >
                通过
              </el-button>
              <el-button
                type="danger"
                size="small"
                plain
                :loading="uploadReviewingId === u.upload_id"
                @click="onUploadReview(u, false)"
              >
                驳回
              </el-button>
            </div>
          </div>
          <div class="meta">
            {{ u.user_name }}（{{ u.user_id }}）· {{ u.upload_id }}
            <template v-if="u.material_name">· 关联物料：{{ u.material_name }}</template>
            <template v-else>· 未关联物料</template>
          </div>
          <div class="times">
            <span>类型 {{ u.file_type }}</span>
            <span>大小 {{ fmtSize(u.file_size) }}</span>
            <span>上传于 {{ fmt(u.created_at) }}</span>
          </div>
          <div v-if="u.parsed_text" class="reason">提炼稿预览：{{ u.parsed_text.slice(0, 400) }}{{ u.parsed_text.length > 400 ? '…' : '' }}</div>
        </el-card>
        <el-empty v-if="!uploadsLoading && uploads.length === 0" description="没有待审核的资料">
          <span class="empty-hint">学生上传的资料会流转到这里，通过后自动转为知识卡片并入向量库。</span>
        </el-empty>
      </div>

      <!-- 驳回理由弹窗 -->
      <el-dialog v-model="uploadRejectDialog" title="驳回资料" width="90%">
        <p>确认驳回「{{ uploadRejectTarget?.filename }}」？</p>
        <el-input
          v-model="uploadRejectNote"
          type="textarea"
          :rows="3"
          placeholder="驳回理由（可选）"
        />
        <template #footer>
          <el-button @click="uploadRejectDialog = false">取消</el-button>
          <el-button type="danger" :loading="uploadReviewingId === uploadRejectTarget?.upload_id" @click="onUploadRejectConfirm">
            确认驳回
          </el-button>
        </template>
      </el-dialog>
    </main>
  </div>
</template>

<style scoped>
.admin {
  display: flex;
  min-height: 100vh; /* 侧栏贴左撑满整屏，内容多时随内容增高 */
}
.sidebar {
  width: 170px;
  flex-shrink: 0;
  background: var(--lx-bg-page);
  border-right: 1px solid var(--lx-border-light);
  padding: var(--lx-space-4) var(--lx-space-3);
  display: flex;
  flex-direction: column;
}
.side-title {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-bold);
  color: var(--lx-green);
  padding: 0 var(--lx-space-3) var(--lx-space-3);
}
.menu {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-1);
}
.side-main {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  min-width: 0;
}
/* mono 功能序号：与侧栏文字同级的仪器标注 */
.side-idx {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.08em;
  color: var(--lx-text-placeholder);
  flex-shrink: 0;
}
.side-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item {
  padding: var(--lx-space-2) var(--lx-space-3);
  border-radius: var(--lx-radius-md);
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-left: 3px solid transparent;
}
.item:hover {
  background: var(--lx-bg-hover);
}
.item.active {
  background: var(--lx-green-light-9); /* 浅绿底选中态 */
  color: var(--lx-green);
  font-weight: var(--lx-font-bold);
  border-left-color: var(--lx-green); /* 高亮绿色左边条 */
}
.item.active .side-idx {
  color: var(--lx-green);
}
.side-badge {
  margin-left: var(--lx-space-2);
}
.side-foot {
  margin-top: auto;
  display: flex;
  flex-direction: column;
}
.back {
  padding: var(--lx-space-2) var(--lx-space-3);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
  text-decoration: none;
  border-radius: var(--lx-radius-md);
}
.back:hover {
  color: var(--lx-green);
  background: var(--lx-green-light-9);
}
/* 退出登录：与"返回学生端"同款文字按钮，button 元素需清默认样式 */
.back-btn {
  font-family: inherit;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
}
.back-btn:hover {
  color: var(--lx-danger);
  background: var(--lx-danger-bg);
}
.content {
  flex: 1;
  min-width: 0;
  padding: var(--lx-space-5);
}
.batch,
.create {
  max-width: 760px;
}
.form-row {
  display: flex;
  align-items: center;
  gap: var(--lx-space-3);
  margin-bottom: var(--lx-space-3);
  font-size: var(--lx-text-sm);
}
.label {
  width: 64px;
  flex-shrink: 0;
  color: var(--lx-text-regular);
}
.wide {
  width: 320px;
}
.inline-hint {
  color: var(--lx-text-placeholder);
  font-size: var(--lx-text-xs);
}
.table-wrap {
  margin: var(--lx-space-4) 0;
}
/* 批量借出表格筛选框：窄条工具输入，不抢表格焦点 */
.batch-filter {
  width: 260px;
  margin-bottom: var(--lx-space-2);
}
/* 空状态引导提示：mono 弱文本，给管理员指路 */
.empty-hint {
  display: block;
  margin-top: var(--lx-space-2);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-placeholder);
}
.actions {
  display: flex;
  gap: var(--lx-space-2);
  align-items: center;
}
.results {
  margin-top: var(--lx-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
}
.result-line {
  font-size: var(--lx-text-sm);
  padding: var(--lx-space-2) var(--lx-space-3);
  border-radius: var(--lx-radius-md);
}
.result-line.ok {
  color: var(--lx-green);
  background: var(--lx-green-light-9);
}
.result-line.fail {
  color: var(--lx-danger);
  background: var(--lx-danger-bg);
}
.res-name {
  font-weight: var(--lx-font-bold);
  margin-right: var(--lx-space-3);
}
.res-id {
  margin-left: var(--lx-space-2);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-bold);
}
.meta {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
  margin-top: var(--lx-space-1);
}
.times {
  display: flex;
  gap: var(--lx-space-3);
  color: var(--lx-text-regular);
  font-size: var(--lx-text-sm);
  margin-top: var(--lx-space-2);
}
.reason {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
  margin-top: var(--lx-space-2);
}
.hint {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-sm);
  margin: 0 0 var(--lx-space-2);
}
</style>

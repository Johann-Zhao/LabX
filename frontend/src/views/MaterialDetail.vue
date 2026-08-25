<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { borrowMaterial, fetchMaterial, uploadFile } from '../api'
import { currentUser, lastBorrowResult } from '../store'
import BorrowDialog from '../components/BorrowDialog.vue'
import MaterialImage from '../components/MaterialImage.vue'

const route = useRoute()
const router = useRouter()
const material = ref(null)
const loading = ref(true)
const borrowing = ref(false)

// 上传资料：文件选择、预览、提交
const uploadDialog = ref(false)
const uploadFileInput = ref(null)
const uploadSelected = ref(null) // { file, name, size, previewUrl? }
const uploading = ref(false)
const uploadThanks = ref('')

// 借期选择（≤30 天直接借出，>30 天填理由转人工审核）
const durationDialog = ref(false)
const borrowDays = ref(30)
const borrowReason = ref('')

const LEVEL_TEXT = { basic: '基础级', advanced: '进阶级', professional: '专业级' }

// 安全确认弹窗（进阶级物料首次借用，1002）
const safetyDialog = ref(false)
const safetyNotice = ref('')
const safetyChecked = ref(false)

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
  durationDialog.value = true // 先选借期，确认后在 onDurationConfirm 里发起借用
}

function onUploadClick() {
  uploadDialog.value = true
  uploadSelected.value = null
  uploadThanks.value = ''
}

function onUploadFileChange(e) {
  const f = e.target.files?.[0]
  if (!f) return
  const okTypes = [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain', 'text/markdown',
  ]
  if (!okTypes.includes(f.type) && !/\.(jpg|jpeg|png|gif|webp|pdf|docx|txt|md)$/i.test(f.name)) {
    ElMessage.warning('不支持的文件格式，请上传图片、PDF、Word 或 TXT')
    e.target.value = ''
    return
  }
  if (f.size > 10 * 1024 * 1024) {
    ElMessage.warning('文件超过 10MB 限制')
    e.target.value = ''
    return
  }
  uploadSelected.value = {
    file: f,
    name: f.name,
    size: f.size,
    previewUrl: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
  }
  e.target.value = ''
}

function removeUploadFile() {
  if (uploadSelected.value?.previewUrl) URL.revokeObjectURL(uploadSelected.value.previewUrl)
  uploadSelected.value = null
}

async function onUploadSubmit() {
  if (!uploadSelected.value || !material.value) return
  uploading.value = true
  try {
    const res = await uploadFile(currentUser.id, uploadSelected.value.file, material.value.material_id)
    if (res.code === 0) {
      uploadThanks.value = res.msg
      removeUploadFile()
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('上传失败：' + e.message)
  } finally {
    uploading.value = false
  }
}

function onUploadClose() {
  removeUploadFile()
  uploadThanks.value = ''
  uploadDialog.value = false
}

async function onDurationConfirm({ days, reason }) {
  borrowDays.value = days
  borrowReason.value = reason
  await doBorrow(false)
}

async function doBorrow(safetyConfirmed) {
  borrowing.value = true
  try {
    const res = await borrowMaterial(
      currentUser.id, material.value.material_id, safetyConfirmed, borrowDays.value, borrowReason.value
    )
    if (res.code === 0 && res.data.status === 'pending') {
      // 超期借用：已提交人工审核，不算借出
      safetyDialog.value = false
      ElMessageBox.alert(res.msg, '已提交审核', { confirmButtonText: '查看我的借用', type: 'info' })
        .then(() => router.push('/records')).catch(() => {})
    } else if (res.code === 0) {
      Object.assign(lastBorrowResult, {
        record_id: res.data.record_id,
        material_id: material.value.material_id,
        material_name: material.value.name,
        due_at: res.data.due_at,
        knowledge_card: res.data.knowledge_card,
      })
      safetyDialog.value = false
      router.push('/borrow/result')
    } else if (res.code === 1002) {
      // 首次借用该类物料：弹一屏安全要点，勾选"我已知晓"后重试
      safetyNotice.value = res.data?.safety_notice || '请按规范操作，用完务必归位。'
      safetyChecked.value = false
      safetyDialog.value = true
    } else if (res.code === 1003) {
      ElMessageBox.alert(res.msg, '需要教师审批', { confirmButtonText: '知道了', type: 'warning' })
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
  <div v-loading="loading" class="detail">
    <template v-if="material">
      <!-- 头图区：4:3 裁切区，object-fit contain 配浅色底；图片缺失时降级为首字符占位块 -->
      <MaterialImage :material-id="material.material_id" :name="material.name" fit="contain" class="hero" />

      <!-- 信息区：名称 → 编号/型号/分类 → 描述 → 关键事实格 -->
      <div class="head-row">
        <h1 class="name">{{ material.name }}</h1>
        <span :class="['level-badge', 'lv-' + material.access_level]">{{ LEVEL_TEXT[material.access_level] || material.access_level }}</span>
      </div>
      <div class="meta">
        <span class="lx-num">{{ material.material_id }}</span> · {{ material.model || '无型号' }} · {{ material.category }}
      </div>
      <p class="desc">{{ material.description }}</p>

      <dl class="facts lx-brackets">
        <div class="fact">
          <dt>存放位置</dt>
          <dd>{{ material.location }}</dd>
        </div>
        <div class="fact">
          <dt>库存</dt>
          <dd>
            <span :class="['stock', 'lx-num', { empty: material.available_quantity === 0 }]">
              {{ material.available_quantity === 0 ? '借空' : `可借 ${material.available_quantity}/${material.total_quantity}` }}
            </span>
          </dd>
        </div>
        <div class="fact">
          <dt>社区经验</dt>
          <dd><span class="lx-num">{{ material.tips_count }}</span> 条</dd>
        </div>
      </dl>

      <!-- 数字分身知识卡片：点击进入全文页（保姆级教程） -->
      <section v-if="material.knowledge_cards?.length" class="cards">
        <div class="cards-title">
          <span>知识卡片</span>
          <span class="title-tag lx-num">共 {{ material.knowledge_cards.length }} 张</span>
        </div>
        <div
          v-for="c in material.knowledge_cards"
          :key="c.card_id"
          class="kcard"
          @click="router.push(`/cards/${c.card_id}`)"
        >
          <span class="kcard-title">{{ c.title }}</span>
          <span class="kcard-id lx-num" aria-hidden="true">{{ c.card_id }}</span>
          <span class="arrow">→</span>
        </div>
      </section>

      <div class="actions">
        <el-button
          type="primary"
          size="large"
          class="act-borrow"
          :disabled="material.available_quantity === 0"
          :loading="borrowing"
          @click="onBorrow"
        >
          {{ material.available_quantity === 0 ? '暂时缺货' : '确认借用' }}
        </el-button>
        <el-button
          size="large"
          plain
          class="act-upload"
          @click="onUploadClick"
        >
          上传资料
        </el-button>
        <el-button
          size="large"
          plain
          class="act-ask"
          @click="router.push({ path: '/', query: { material_id: material.material_id } })"
        >
          问问 AI
        </el-button>
      </div>

      <!-- 上传资料弹窗：选择文件 → 显示鼓励文案 -->
      <el-dialog v-model="uploadDialog" :title="`上传资料：${material.name}`" width="90%" @close="onUploadClose">
        <div v-if="!uploadThanks" class="upload-area">
          <input
            ref="uploadFileInput"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp,.pdf,.docx,.txt,.md"
            style="display:none"
            @change="onUploadFileChange"
          />
          <el-button size="large" @click="uploadFileInput?.click()">选择文件</el-button>
          <p class="upload-hint">支持图片、PDF、Word、TXT，不超过 10MB。审核通过后将并入该物料的知识库。</p>
          <div v-if="uploadSelected" class="upload-preview">
            <img v-if="uploadSelected.previewUrl" :src="uploadSelected.previewUrl" class="upload-thumb" alt="预览" />
            <span v-else class="upload-icon">📄</span>
            <span class="upload-name" :title="uploadSelected.name">{{ uploadSelected.name }}</span>
            <span class="upload-size lx-num">{{ (uploadSelected.size / 1024).toFixed(1) }} KB</span>
            <button type="button" class="upload-remove" aria-label="移除" @click="removeUploadFile">×</button>
          </div>
        </div>
        <div v-else class="upload-thanks">
          <p>{{ uploadThanks }}</p>
        </div>
        <template #footer>
          <template v-if="!uploadThanks">
            <el-button @click="onUploadClose">取消</el-button>
            <el-button type="primary" :disabled="!uploadSelected" :loading="uploading" @click="onUploadSubmit">
              提交
            </el-button>
          </template>
          <template v-else>
            <el-button @click="uploadThanks = ''; removeUploadFile()">再传一份</el-button>
            <el-button type="primary" @click="onUploadClose">完成</el-button>
          </template>
        </template>
      </el-dialog>

      <!-- 借期选择：≤30 天直接借出，>30 天填理由转人工审核 -->
      <BorrowDialog v-model="durationDialog" :title="`借用「${material.name}」`" @confirm="onDurationConfirm" />

      <!-- 进阶级物料首次借用：10 秒安全确认（一屏要点 + 勾选） -->
      <el-dialog v-model="safetyDialog" title="安全确认（首次借用该类物料）" width="90%">
        <p class="safety-text">{{ safetyNotice }}</p>
        <el-checkbox v-model="safetyChecked">我已知晓以上安全要点</el-checkbox>
        <template #footer>
          <el-button @click="safetyDialog = false">取消</el-button>
          <el-button type="primary" :disabled="!safetyChecked" :loading="borrowing" @click="doBorrow(true)">
            确认并借用
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<style scoped>
/* 头图区：4:3，宽屏下用 max-height 兜住高度；占位大字随头图放大 */
.hero {
  aspect-ratio: 4 / 3;
  max-height: 340px;
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  margin-bottom: var(--lx-space-4);
  --mimg-fs: var(--lx-text-4xl);
}

.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--lx-space-2);
}
.name {
  margin: 0;
  font-size: var(--lx-text-xl);
  font-weight: var(--lx-font-bold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
/* 等级徽标：与列表页同款双段式（mono 代码 + 中文），颜色走语义派生令牌 */
.level-badge {
  flex-shrink: 0;
  padding: 0 var(--lx-space-2);
  border: 1px solid;
  border-radius: 3px;
  font-size: var(--lx-text-xs);
  line-height: 1.6;
  align-self: center;
}
.lv-basic.level-badge {
  color: var(--lx-green);
  background: var(--lx-green-light-9);
  border-color: var(--lx-green-light-8);
}
.lv-advanced.level-badge {
  color: var(--lx-warning);
  background: var(--lx-warning-bg);
  border-color: var(--el-color-warning-light-7);
}
.lv-professional.level-badge {
  color: var(--lx-danger);
  background: var(--lx-danger-bg);
  border-color: var(--el-color-danger-light-7);
}
.meta {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-sm);
  margin-top: var(--lx-space-1);
}
.desc {
  color: var(--lx-text-regular);
  font-size: var(--lx-text-base);
  margin: var(--lx-space-3) 0 0;
}

/* 关键事实：浅色内嵌区块里的自适应网格，不堆边框线 */
.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--lx-space-3);
  margin: var(--lx-space-4) 0 0;
  padding: var(--lx-space-3) var(--lx-space-4);
  background: var(--lx-bg-subtle);
  border-radius: var(--lx-radius-md);
}
.fact dt {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  margin-bottom: var(--lx-space-1);
}
.fact dd {
  margin: 0;
  font-size: var(--lx-text-base);
  color: var(--lx-text-primary);
  font-weight: var(--lx-font-medium);
}
/* 库存状态标签：与列表页同一套令牌样式 */
.stock {
  font-size: var(--lx-text-xs);
  font-weight: var(--lx-font-medium);
  padding: var(--lx-space-1) var(--lx-space-2);
  border-radius: var(--lx-radius-sm);
  color: var(--lx-success);
  background: var(--lx-green-light-9);
  white-space: nowrap;
}
.stock.empty {
  color: var(--lx-danger);
  background: var(--lx-danger-bg);
}

/* 知识卡片列表 */
.cards {
  margin-top: var(--lx-space-5);
}
.cards-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: var(--lx-text-sm);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-secondary);
  margin-bottom: var(--lx-space-2);
}
/* mono 功能标签：真实卡片计数 */
.title-tag {
  font-size: var(--lx-text-xs);
  font-weight: var(--lx-font-regular);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}
.kcard {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--lx-space-2);
  padding: var(--lx-space-2) var(--lx-space-3);
  margin-bottom: var(--lx-space-2);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-base);
  cursor: pointer;
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
  transition:
    border-color var(--lx-duration-fast) var(--lx-ease-out),
    background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.kcard:hover {
  border-color: var(--lx-green-light-3);
  background: var(--lx-green-light-9);
}
.kcard-title {
  flex: 1;
  min-width: 0; /* 长标题在 flex 里收缩省略，不挤掉编号 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 卡片编号：真实 card_id 的 mono 标注，窄屏隐藏保标题完整 */
.kcard-id {
  flex-shrink: 0;
  font-size: var(--lx-text-xs);
  color: var(--lx-text-placeholder);
}
@media (max-width: 767px) {
  .kcard-id {
    display: none;
  }
}
.kcard .arrow {
  color: var(--lx-green);
  font-family: var(--lx-font-mono);
  line-height: 1;
  flex-shrink: 0;
}

/* 操作区：主/次两级按钮层级——主操作占 2 份宽度独占强调，次操作占 1 份描边降权 */
.actions {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
  margin-top: var(--lx-space-5);
  padding-top: var(--lx-space-4);
  border-top: 1px solid var(--lx-border-light);
}
.actions .el-button {
  margin-left: 0;
}
@media (min-width: 640px) {
  .actions {
    flex-direction: row;
  }
  .actions .act-borrow {
    flex: 2;
  }
  .actions .act-upload {
    flex: 1;
  }
  .actions .act-ask {
    flex: 1;
  }
}

/* 上传资料弹窗 */
.upload-area {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}
.upload-hint {
  margin: 0;
  font-size: var(--lx-text-sm);
  color: var(--lx-text-secondary);
}
.upload-preview {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  padding: var(--lx-space-2) var(--lx-space-3);
  background: var(--lx-bg-subtle);
  border-radius: var(--lx-radius-sm);
}
.upload-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: var(--lx-radius-sm);
  border: 1px solid var(--lx-border-light);
}
.upload-icon {
  font-size: var(--lx-text-lg);
}
.upload-name {
  flex: 1;
  min-width: 0;
  font-size: var(--lx-text-sm);
  color: var(--lx-text-regular);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.upload-size {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-placeholder);
  flex-shrink: 0;
}
.upload-remove {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  font-size: var(--lx-text-lg);
  color: var(--lx-text-placeholder);
  cursor: pointer;
  line-height: 1;
  flex-shrink: 0;
}
.upload-remove:hover {
  color: var(--lx-danger);
}
.upload-thanks {
  padding: var(--lx-space-4) 0;
  text-align: center;
  font-size: var(--lx-text-base);
  color: var(--lx-text-regular);
  line-height: var(--lx-leading);
}

.safety-text {
  white-space: pre-wrap;
  color: var(--lx-text-regular);
  font-size: var(--lx-text-base);
  line-height: var(--lx-leading);
  margin: 0 0 var(--lx-space-3);
}
</style>

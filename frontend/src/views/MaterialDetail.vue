<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { borrowMaterial, fetchMaterial } from '../api'
import { currentUser, lastBorrowResult } from '../store'
import BorrowDialog from '../components/BorrowDialog.vue'
import MaterialImage from '../components/MaterialImage.vue'

const route = useRoute()
const router = useRouter()
const material = ref(null)
const loading = ref(true)
const borrowing = ref(false)

// 借期选择（≤30 天直接借出，>30 天填理由转人工审核）
const durationDialog = ref(false)
const borrowDays = ref(30)
const borrowReason = ref('')

const LEVEL_TYPE = { basic: 'success', advanced: 'warning', professional: 'danger' }
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
        <el-tag :type="LEVEL_TYPE[material.access_level]" class="level-tag">
          {{ LEVEL_TEXT[material.access_level] || material.access_level }}
        </el-tag>
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
          <span class="title-tag lx-num">CARDS {{ material.knowledge_cards.length }}</span>
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
          :disabled="material.available_quantity === 0"
          :loading="borrowing"
          @click="onBorrow"
        >
          {{ material.available_quantity === 0 ? '暂时缺货' : '确认借用' }}
        </el-button>
        <el-button
          size="large"
          @click="router.push({ path: '/', query: { material_id: material.material_id } })"
        >
          问问 AI（该物料专属助教）
        </el-button>
      </div>

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
.level-tag {
  flex-shrink: 0;
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
}

/* 操作区：窄屏竖排全宽，≥640px 横排均分 */
.actions {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
  margin-top: var(--lx-space-5);
}
.actions .el-button {
  margin-left: 0;
}
@media (min-width: 640px) {
  .actions {
    flex-direction: row;
  }
  .actions .el-button {
    flex: 1;
  }
}

.safety-text {
  white-space: pre-wrap;
  color: var(--lx-text-regular);
  font-size: var(--lx-text-base);
  line-height: var(--lx-leading);
  margin: 0 0 var(--lx-space-3);
}
</style>

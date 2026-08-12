<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { borrowMaterial, fetchMaterial } from '../api'
import { currentUser, lastBorrowResult } from '../store'
import BorrowDialog from '../components/BorrowDialog.vue'

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
  try {
    const res = await fetchMaterial(route.params.id)
    if (res.code === 0) {
      material.value = res.data
    } else {
      ElMessage.error(res.msg)
      router.replace('/')
    }
  } catch (e) {
    // 请求失败（网络错误/后端 5xx）：必须清掉 loading，否则页面永远转圈
    ElMessage.error('物料详情加载失败：' + e.message)
    router.replace('/')
  } finally {
    loading.value = false
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

        <!-- 数字分身知识卡片：点击进入全文页（保姆级教程） -->
        <div v-if="material.knowledge_cards?.length" class="cards">
          <div
            v-for="c in material.knowledge_cards"
            :key="c.card_id"
            class="kcard"
            @click="router.push(`/cards/${c.card_id}`)"
          >
            <span>{{ c.title }}</span>
            <span class="arrow">→</span>
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
        <el-button
          size="large"
          class="ask-btn"
          @click="router.push({ path: '/ask', query: { material_id: material.material_id } })"
        >
          问问 AI（该物料专属助教）
        </el-button>
      </el-card>

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
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}
.kcard:hover {
  border-color: #42b883;
}
.kcard .arrow {
  color: #42b883;
}
.borrow-btn {
  width: 100%;
  margin-top: 16px;
}
.ask-btn {
  width: 100%;
  margin-top: 8px;
  margin-left: 0;
}
.safety-text {
  white-space: pre-wrap;
  color: #606266;
  font-size: 14px;
  line-height: 1.8;
  margin: 0 0 12px;
}
</style>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

// 借期选择弹窗：≤30 天直接借出；>30 天需填理由，人工审核通过后才算借出（API.md 第 3 节）
// 用法：<BorrowDialog v-model="show" title="…" @confirm="onConfirm({days, reason})" />
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '选择借用时长' },
})
const emit = defineEmits(['update:modelValue', 'confirm'])

const PRESETS = [7, 14, 30]
const choice = ref('30') // '7' | '14' | '30' | 'more'
const customDays = ref(60)
const reason = ref('')

// 语义化借期场景：一次点选同时填好天数与理由（>30 天自动转审核）
const SCENARIOS = [
  { label: '课程设计', days: 30, reason: '' },
  { label: '竞赛项目', days: 60, reason: '竞赛项目需要长期使用' },
  { label: '长期研究', days: 90, reason: '长期研究项目需要连续使用' },
]
function applyScenario(s) {
  if (s.days > 30) {
    choice.value = 'more'
    customDays.value = s.days
    reason.value = s.reason
  } else {
    choice.value = String(s.days)
    reason.value = ''
  }
}

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const needReason = computed(() => choice.value === 'more')

// 每次打开重置为默认 30 天，避免带上次的理由
watch(visible, (v) => {
  if (v) {
    choice.value = '30'
    customDays.value = 60
    reason.value = ''
  }
})

function onConfirm() {
  const days = needReason.value ? customDays.value : Number(choice.value)
  if (needReason.value && !reason.value.trim()) {
    ElMessage.warning('超过一个月需填写申请理由，审核通过后才算借出')
    return
  }
  visible.value = false
  emit('confirm', { days, reason: reason.value.trim() })
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="90%">
    <div class="tip">一个月以内直接借出；超过一个月需填写理由，人工审核通过后才算借出。</div>
    <!-- 场景预设：常见用途一次点选（天数+理由一起填好，可再改） -->
    <div class="scenarios">
      <span class="sc-label lx-num" aria-hidden="true">场景</span>
      <button
        v-for="s in SCENARIOS"
        :key="s.label"
        type="button"
        class="sc-chip"
        @click="applyScenario(s)"
      >
        {{ s.label }} · {{ s.days }}天
      </button>
    </div>
    <el-radio-group v-model="choice" class="choices">
      <el-radio v-for="d in PRESETS" :key="d" :value="String(d)">{{ d }} 天</el-radio>
      <el-radio value="more">更久…</el-radio>
    </el-radio-group>
    <!-- 超期借用区：警告色底 + 左侧警示条，提示"要审核"这件事 -->
    <div v-if="needReason" class="more-box">
      <div class="row">
        <span>借用天数</span>
        <el-input-number v-model="customDays" :min="31" :max="180" size="small" />
        <span class="hint">最长 180 天</span>
      </div>
      <el-input
        v-model="reason"
        type="textarea"
        :rows="3"
        placeholder="申请理由（如：课程设计/竞赛项目需要长期使用），将提交管理员审核"
      />
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onConfirm">确认</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
/* 规则提示：浅色内嵌条，不抢主操作 */
.tip {
  background: var(--lx-bg-subtle);
  border-radius: var(--lx-radius-sm);
  padding: var(--lx-space-2) var(--lx-space-3);
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
  line-height: var(--lx-leading);
  margin: 0 0 var(--lx-space-3);
}
/* 场景预设行：mono 标注 + 胶囊按钮 */
.scenarios {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--lx-space-2);
  margin-bottom: var(--lx-space-3);
}
.sc-label {
  font-size: var(--lx-text-xs);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}
.sc-chip {
  padding: 2px var(--lx-space-3);
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-pill);
  cursor: pointer;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    border-color var(--lx-duration-fast) var(--lx-ease-out),
    background-color var(--lx-duration-fast) var(--lx-ease-out);
}
.sc-chip:hover {
  color: var(--lx-green);
  border-color: var(--lx-green-light-5);
  background: var(--lx-green-light-9);
}
.choices {
  display: flex;
  flex-wrap: wrap;
  gap: var(--lx-space-2) var(--lx-space-4);
  margin-bottom: var(--lx-space-3);
}
/* flex 布局下用 gap 控距，清掉单选默认的右边距 */
.choices :deep(.el-radio) {
  margin-right: 0;
}
/* 超期区：警告令牌色（浅琥珀底 + 左侧警示条） */
.more-box {
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
  background: var(--lx-warning-bg);
  border-left: 3px solid var(--lx-warning);
  border-radius: var(--lx-radius-sm);
  padding: var(--lx-space-3);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--lx-space-2);
  font-size: var(--lx-text-sm);
  color: var(--lx-text-regular);
}
.hint {
  color: var(--lx-text-placeholder);
  font-size: var(--lx-text-xs);
}
</style>

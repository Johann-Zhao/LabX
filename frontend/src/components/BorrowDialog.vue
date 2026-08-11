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
    <el-radio-group v-model="choice" class="choices">
      <el-radio v-for="d in PRESETS" :key="d" :value="String(d)">{{ d }} 天</el-radio>
      <el-radio value="more">更久…</el-radio>
    </el-radio-group>
    <template v-if="needReason">
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
    </template>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onConfirm">确认</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.tip {
  color: #909399;
  font-size: 12px;
  margin: 0 0 10px;
}
.choices {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13px;
}
.hint {
  color: #c0c4cc;
  font-size: 12px;
}
</style>

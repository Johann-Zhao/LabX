<script setup>
import { computed, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { borrowMaterial } from '../api'
import { currentUser } from '../store'
import BorrowDialog from '../components/BorrowDialog.vue'

// 对话内联的 BOM 卡片：实验室可借 / 需自行购买 两组清单 + 一键预约（含借期选择）
const props = defineProps({
  bom: { type: Object, required: true }, // { project_guess, materials[{source,quantity,...}], skills }
})

const labItems = computed(() => props.bom.materials.filter((m) => m.source === 'lab'))
const buyItems = computed(() => props.bom.materials.filter((m) => m.source === 'buy'))
const reservable = computed(() => labItems.value.filter((m) => m.in_stock))

const durationDialog = ref(false)
const reserving = ref(false)
const reserveResults = ref([]) // [{ name, ok, msg }]

function onReserveClick() {
  reserveResults.value = []
  durationDialog.value = true
}

// 逐件预约：按 BOM 数量约（不超过当前可借数），安全确认与借期在所有件间共用
async function onDurationConfirm({ days, reason }) {
  reserving.value = true
  const needConfirm = []
  for (const m of reservable.value) {
    await reserveOne(m, false, days, reason, needConfirm)
  }
  if (needConfirm.length) {
    try {
      await ElMessageBox.confirm(
        needConfirm.map(({ m, notice }) => `【${m.name}】\n${notice}`).join('\n\n'),
        '以下物料首次借用，请完成安全确认',
        { confirmButtonText: '我已知晓，继续预约', cancelButtonText: '跳过这些', type: 'warning' }
      )
      for (const { m } of needConfirm) {
        await reserveOne(m, true, days, reason, [])
      }
    } catch {
      reserveResults.value.push(...needConfirm.map(({ m }) => ({ name: m.name, ok: false, msg: '已跳过安全确认' })))
    }
  }
  reserving.value = false
}

// 预约一件物料：一条记录记 quantity 件（数量不超过当前可借数）；needConfirm 收集待安全确认的物料
async function reserveOne(m, safetyConfirmed, days, reason, needConfirm) {
  const qty = Math.max(1, Math.min(m.quantity || 1, m.available_quantity || 1))
  const label = qty > 1 ? `${m.name} ×${qty}` : m.name
  const res = await borrowMaterial(currentUser.id, m.material_id, safetyConfirmed, days, reason, qty)
  if (res.code === 0) {
    const pending = res.data.status === 'pending'
    reserveResults.value.push({
      name: label,
      ok: !pending ? true : null, // null → 审核中（橙色，不是错误）
      msg: pending ? '已提交审核，通过后算借出' : `预约成功（${res.data.record_id}）`,
    })
  } else if (res.code === 1002 && !safetyConfirmed) {
    needConfirm.push({ m, notice: res.data.safety_notice })
  } else {
    reserveResults.value.push({ name: label, ok: false, msg: res.msg })
  }
}
</script>

<template>
  <div class="bom-card">
    <div class="guess">方案：{{ bom.project_guess }}</div>

    <div v-if="labItems.length" class="group">实验室可借</div>
    <div v-for="m in labItems" :key="m.material_id" class="mrow">
      <span>
        {{ m.name }}<template v-if="m.quantity > 1"> ×{{ m.quantity }}</template>
        <span class="mid">{{ m.material_id }}</span>
        <span v-if="m.purpose" class="purpose">{{ m.purpose }}</span>
      </span>
      <el-tag :type="m.in_stock ? 'success' : 'warning'" size="small">
        {{ m.in_stock ? `可借 ${m.available_quantity}` : '缺货' }}
      </el-tag>
    </div>

    <div v-if="buyItems.length" class="group buy">需自行购买</div>
    <div v-for="m in buyItems" :key="m.name" class="mrow buy-row">
      <span>
        {{ m.name }}<template v-if="m.quantity > 1"> ×{{ m.quantity }}</template>
        <span v-if="m.spec" class="mid">{{ m.spec }}</span>
        <span v-if="m.purpose" class="purpose">{{ m.purpose }}</span>
      </span>
      <el-tag type="info" size="small">需自购</el-tag>
    </div>

    <div v-if="bom.skills?.length" class="skills">
      <el-tag v-for="s in bom.skills" :key="s.name" size="small" type="warning" class="skill">{{ s.name }}</el-tag>
    </div>
    <el-button
      type="success"
      size="small"
      class="reserve-btn"
      :loading="reserving"
      :disabled="!reservable.length"
      @click="onReserveClick"
    >
      一键预约全部在库物料
    </el-button>
    <div v-for="(r, i) in reserveResults" :key="i" class="rrow">
      <span>{{ r.name }}</span>
      <span :class="r.ok === null ? 'pending' : r.ok ? 'ok' : 'fail'">{{ r.msg }}</span>
    </div>
    <div v-if="reserveResults.length" class="hint">到「我的借用」可查看记录并归还</div>

    <BorrowDialog v-model="durationDialog" title="一键预约：选择借用时长" @confirm="onDurationConfirm" />
  </div>
</template>

<style scoped>
.bom-card {
  margin-top: var(--lx-space-2);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border);
  border-radius: var(--lx-radius-md);
  padding: var(--lx-space-3) var(--lx-space-4);
  min-width: 260px;
}
.guess {
  font-size: var(--lx-text-sm);
  color: var(--lx-green);
  font-weight: var(--lx-font-semibold);
  margin-bottom: var(--lx-space-2);
}
.group {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-regular);
  font-weight: var(--lx-font-semibold);
  margin: var(--lx-space-2) 0 var(--lx-space-1);
  border-left: 3px solid var(--lx-green);
  padding-left: var(--lx-space-2);
}
.group.buy {
  border-left-color: var(--lx-border-strong);
}
.mrow,
.rrow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--lx-space-1) 0;
  font-size: var(--lx-text-sm);
  gap: var(--lx-space-2);
}
.buy-row {
  color: var(--lx-text-secondary);
}
.mid {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
  margin-left: var(--lx-space-1);
}
.purpose {
  color: var(--lx-text-placeholder);
  font-size: var(--lx-text-xs);
  margin-left: var(--lx-space-1);
}
.skills {
  margin-top: var(--lx-space-2);
}
.skill {
  margin: 0 var(--lx-space-1) var(--lx-space-1) 0;
}
.reserve-btn {
  width: 100%;
  margin-top: var(--lx-space-3);
}
.ok {
  color: var(--lx-success);
}
.pending {
  color: var(--lx-warning);
}
.fail {
  color: var(--lx-danger);
}
.hint {
  font-size: var(--lx-text-xs);
  color: var(--lx-text-secondary);
  margin-top: var(--lx-space-2);
}
</style>

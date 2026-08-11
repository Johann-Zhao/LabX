<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { borrowMaterial } from '../api'
import { currentUser } from '../store'

// 对话内联的 BOM 卡片：物料清单（含库存）+ 一键预约
const props = defineProps({
  bom: { type: Object, required: true }, // { project_guess, materials, skills }
})

const reserving = ref(false)
const reserveResults = ref([]) // [{ name, ok, msg }]

async function reserveAll() {
  const inStock = props.bom.materials.filter((m) => m.in_stock)
  if (!inStock.length) return
  reserving.value = true
  reserveResults.value = []
  const needConfirm = []
  for (const m of inStock) {
    const res = await borrowMaterial(currentUser.id, m.material_id)
    if (res.code === 0) {
      reserveResults.value.push({ name: m.name, ok: true, msg: `预约成功（${res.data.record_id}）` })
    } else if (res.code === 1002) {
      needConfirm.push({ ...m, notice: res.data.safety_notice })
    } else {
      reserveResults.value.push({ name: m.name, ok: false, msg: res.msg })
    }
  }
  if (needConfirm.length) {
    try {
      await ElMessageBox.confirm(
        needConfirm.map((m) => `【${m.name}】\n${m.notice}`).join('\n\n'),
        '以下物料首次借用，请完成安全确认',
        { confirmButtonText: '我已知晓，继续预约', cancelButtonText: '跳过这些', type: 'warning' }
      )
      for (const m of needConfirm) {
        const res = await borrowMaterial(currentUser.id, m.material_id, true)
        reserveResults.value.push(
          res.code === 0
            ? { name: m.name, ok: true, msg: `预约成功（${res.data.record_id}）` }
            : { name: m.name, ok: false, msg: res.msg }
        )
      }
    } catch {
      reserveResults.value.push(...needConfirm.map((m) => ({ name: m.name, ok: false, msg: '已跳过安全确认' })))
    }
  }
  reserving.value = false
}
</script>

<template>
  <div class="bom-card">
    <div class="guess">方案：{{ bom.project_guess }}</div>
    <div v-for="m in bom.materials" :key="m.material_id" class="mrow">
      <span>{{ m.name }} <span class="mid">{{ m.material_id }}</span></span>
      <el-tag :type="m.in_stock ? 'success' : 'info'" size="small">
        {{ m.in_stock ? `可借 ${m.available_quantity}` : '缺货' }}
      </el-tag>
    </div>
    <div v-if="bom.skills?.length" class="skills">
      <el-tag v-for="s in bom.skills" :key="s.name" size="small" type="warning" class="skill">{{ s.name }}</el-tag>
    </div>
    <el-button
      type="success"
      size="small"
      class="reserve-btn"
      :loading="reserving"
      :disabled="!bom.materials.some((m) => m.in_stock)"
      @click="reserveAll"
    >
      一键预约全部在库物料
    </el-button>
    <div v-for="(r, i) in reserveResults" :key="i" class="rrow">
      <span>{{ r.name }}</span>
      <span :class="r.ok ? 'ok' : 'fail'">{{ r.msg }}</span>
    </div>
    <div v-if="reserveResults.length" class="hint">到「我的借用」可查看记录并归还</div>
  </div>
</template>

<style scoped>
.bom-card {
  margin-top: 6px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 10px 12px;
  min-width: 260px;
}
.guess {
  font-size: 13px;
  color: #42b883;
  font-weight: bold;
  margin-bottom: 6px;
}
.mrow,
.rrow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
}
.mid {
  color: #909399;
  font-size: 11px;
}
.skills {
  margin-top: 6px;
}
.skill {
  margin: 0 4px 4px 0;
}
.reserve-btn {
  width: 100%;
  margin-top: 8px;
}
.ok {
  color: #42b883;
}
.fail {
  color: #f56c6c;
}
.hint {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}
</style>

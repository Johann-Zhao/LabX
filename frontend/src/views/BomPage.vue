<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { borrowMaterial, recommendBom } from '../api'
import { currentUser } from '../store'

const description = ref('')
const loading = ref(false)
const result = ref(null) // { project_guess, materials, skills, reference_projects }
const reserving = ref(false)
const reserveResults = ref([]) // [{ name, ok, msg }]

async function generate() {
  if (!description.value.trim() || loading.value) return
  loading.value = true
  result.value = null
  reserveResults.value = []
  try {
    const res = await recommendBom(description.value.trim(), currentUser.id)
    if (res.code === 0) {
      result.value = res.data
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    loading.value = false
  }
}

// 一键预约：逐个借用所有在库物料；遇进阶级首次借用（1002）收集起来统一确认后重试
async function reserveAll() {
  const inStock = result.value.materials.filter((m) => m.in_stock)
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
  <div>
    <el-input
      v-model="description"
      type="textarea"
      :rows="3"
      placeholder="用一句话描述你想做的东西，如：我想做一个能自动浇花的装置"
      @keyup.ctrl.enter="generate"
    />
    <el-button type="primary" size="large" class="gen-btn" :loading="loading" @click="generate">
      {{ loading ? '正在生成方案…' : '生成物料方案' }}
    </el-button>

    <template v-if="result">
      <el-card class="block" shadow="never">
        <template #header>项目方案</template>
        <p class="guess">{{ result.project_guess }}</p>
      </el-card>

      <el-card class="block" shadow="never">
        <template #header>推荐物料（已校验库存）</template>
        <div v-for="m in result.materials" :key="m.material_id" class="mrow">
          <span>{{ m.name }} <span class="mid">{{ m.material_id }}</span></span>
          <el-tag :type="m.in_stock ? 'success' : 'info'" size="small">
            {{ m.in_stock ? `可借 ${m.available_quantity} 件` : '缺货，可排队' }}
          </el-tag>
        </div>
        <el-button
          type="success"
          class="reserve-btn"
          :loading="reserving"
          :disabled="!result.materials.some((m) => m.in_stock)"
          @click="reserveAll"
        >
          一键预约全部在库物料
        </el-button>
      </el-card>

      <el-card v-if="result.skills?.length" class="block" shadow="never">
        <template #header>你需要掌握的技能</template>
        <el-tag v-for="s in result.skills" :key="s.name" class="skill" type="warning">{{ s.name }}</el-tag>
      </el-card>

      <el-card v-if="reserveResults.length" class="block" shadow="never">
        <template #header>预约结果</template>
        <div v-for="(r, i) in reserveResults" :key="i" class="mrow">
          <span>{{ r.name }}</span>
          <span :class="r.ok ? 'ok' : 'fail'">{{ r.msg }}</span>
        </div>
        <el-button class="reserve-btn" @click="$router.push('/records')">查看我的借用</el-button>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.gen-btn {
  width: 100%;
  margin-top: 10px;
}
.block {
  margin-top: 12px;
}
.guess {
  margin: 0;
  color: #606266;
}
.mrow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 14px;
}
.mid {
  color: #909399;
  font-size: 12px;
}
.reserve-btn {
  width: 100%;
  margin-top: 10px;
}
.skill {
  margin: 0 6px 6px 0;
}
.ok {
  color: #42b883;
}
.fail {
  color: #f56c6c;
}
</style>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchMaterials } from '../api'
import MaterialImage from '../components/MaterialImage.vue'

const router = useRouter()
const keyword = ref('')
const materials = ref([])
const loading = ref(false)

// 借阅等级标签颜色
const LEVEL_TYPE = { basic: 'success', advanced: 'warning', professional: 'danger' }
const LEVEL_TEXT = { basic: '基础级', advanced: '进阶级', professional: '专业级' }

async function load() {
  loading.value = true
  try {
    const res = await fetchMaterials(keyword.value.trim())
    if (res.code === 0) {
      materials.value = res.data
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    loading.value = false
  }
}

// 卡片整卡可点进详情；同时支持键盘 Enter（焦点态由全局 :focus-visible 描边兜底）
function open(id) {
  router.push(`/materials/${id}`)
}

// 搜索无结果时的引导动作：清空关键词并重新拉全量列表
function clearSearch() {
  keyword.value = ''
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <!-- 搜索框：大号输入 + 前缀放大镜（内联 SVG，不引图标库） -->
    <el-input
      v-model="keyword"
      placeholder="搜索物料名称或型号，如 DHT22"
      clearable
      size="large"
      class="search"
      @keyup.enter="load"
      @clear="load"
    >
      <template #prefix>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <line x1="16.5" y1="16.5" x2="21" y2="21" />
        </svg>
      </template>
      <template #append>
        <el-button @click="load">搜索</el-button>
      </template>
    </el-input>

    <div v-loading="loading" class="list">
      <!-- 物料卡片：仪器角标（lx-brackets）+ 左缩略图（72px 方图，加载失败自动降级占位）+ 右信息区 -->
      <article
        v-for="m in materials"
        :key="m.material_id"
        class="card lx-brackets"
        tabindex="0"
        @click="open(m.material_id)"
        @keyup.enter="open(m.material_id)"
      >
        <MaterialImage :material-id="m.material_id" :name="m.name" class="thumb" />
        <div class="info">
          <div class="head">
            <span class="name">{{ m.name }}</span>
            <el-tag :type="LEVEL_TYPE[m.access_level]" size="small" class="level-tag">
              {{ LEVEL_TEXT[m.access_level] || m.access_level }}
            </el-tag>
          </div>
          <div class="meta"><span class="lx-num">{{ m.material_id }}</span> · {{ m.model || '无型号' }} · {{ m.category }}</div>
          <div class="desc">{{ m.description }}</div>
          <div class="foot">
            <span class="location"><span class="loc-tag lx-num" aria-hidden="true">LOC</span>{{ m.location }}</span>
            <span :class="['stock', 'lx-num', { empty: m.available_quantity === 0 }]">
              {{ m.available_quantity === 0 ? '借空' : `可借 ${m.available_quantity}/${m.total_quantity}` }}
            </span>
          </div>
        </div>
      </article>
      <el-empty v-if="!loading && materials.length === 0" description="没有找到匹配的物料">
        <el-button v-if="keyword" @click="clearSearch">清除搜索条件</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.search {
  max-width: 560px; /* 宽屏下搜索框不拉满，保持工具感 */
}

.list {
  margin-top: var(--lx-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-3);
}

/* 物料卡片：细边框分组，hover 微抬升 + 细阴影（150ms） */
.card {
  display: flex;
  gap: var(--lx-space-3);
  padding: var(--lx-space-3);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  cursor: pointer;
  transition:
    transform var(--lx-duration-fast) var(--lx-ease-out),
    box-shadow var(--lx-duration-fast) var(--lx-ease-out),
    border-color var(--lx-duration-fast) var(--lx-ease-out);
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--lx-shadow-1);
  border-color: var(--lx-border-strong);
}

.thumb {
  width: 72px;
  height: 72px;
  border-radius: var(--lx-radius-sm);
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0; /* 让长文本能在 flex 里正确收缩换行 */
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--lx-space-2);
}
.level-tag {
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
/* 描述最多两行，超出省略，保持卡片高度整齐 */
.desc {
  color: var(--lx-text-regular);
  font-size: var(--lx-text-sm);
  margin-top: var(--lx-space-1);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--lx-space-2);
  margin-top: var(--lx-space-2);
}
.location {
  color: var(--lx-text-secondary);
  font-size: var(--lx-text-xs);
}
/* 库位功能标注：mono 小号 LOC 前缀，后面跟真实位置文本 */
.loc-tag {
  letter-spacing: 0.08em;
  color: var(--lx-text-placeholder);
  margin-right: var(--lx-space-1);
}
/* 库存状态标签：可借=浅绿底主绿字；借空=浅红底危险色字 */
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

/* 窄屏缩略图降一档，卡片不溢出 */
@media (max-width: 480px) {
  .thumb {
    width: 64px;
    height: 64px;
  }
}
</style>

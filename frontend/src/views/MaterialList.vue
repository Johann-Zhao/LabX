<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchMaterials } from '../api'
import MaterialImage from '../components/MaterialImage.vue'

const router = useRouter()
const keyword = ref('')
const category = ref('全部')
const all = ref([])
const loading = ref(true)

// 借阅等级徽标（自定义双段式：mono 代码 + 中文，区分度比 el-tag 更高）
const LEVEL_TEXT = { basic: '基础级', advanced: '进阶级', professional: '专业级' }

// 分类列表：从数据里动态去重（"全部"永远在最前）
const categories = computed(() => ['全部', ...new Set(all.value.map(m => m.category).filter(Boolean))])

// 即时过滤：关键字 + 分类全部在本地算（数据量小，比服务端往返更快更跟手）
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return all.value.filter(m => {
    const inCategory = category.value === '全部' || m.category === category.value
    if (!inCategory) return false
    if (!kw) return true
    return [m.name, m.model, m.description, m.category, m.location, m.material_id]
      .some(v => String(v || '').toLowerCase().includes(kw))
  })
})

async function load() {
  loading.value = true
  try {
    const res = await fetchMaterials('')
    if (res.code === 0) {
      all.value = res.data
    } else {
      ElMessage.error(res.msg)
    }
  } catch (e) {
    ElMessage.error('网络错误：' + e.message)
  } finally {
    loading.value = false
  }
}

function open(id) {
  router.push(`/materials/${id}`)
}

// 无结果时的引导动作：清空全部筛选条件
function clearFilters() {
  keyword.value = ''
  category.value = '全部'
}

onMounted(load)
</script>

<template>
  <div>
    <!-- 工具栏：大号即时搜索 + 实时计数读数（mono） -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="输入关键词即时筛选：名称 / 型号 / 描述 / 库位"
        clearable
        size="large"
        class="search"
      >
        <template #prefix>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <line x1="16.5" y1="16.5" x2="21" y2="21" />
          </svg>
        </template>
      </el-input>
      <span class="count lx-num" aria-live="polite">共 {{ filtered.length }} 件</span>
    </div>

    <!-- 分类筛选 chips：仪器分段语言，点选即过滤 -->
    <div class="chips">
      <button
        v-for="c in categories"
        :key="c"
        type="button"
        class="chip lx-num"
        :class="{ active: category === c }"
        @click="category = c"
      >
        {{ c }}
      </button>
    </div>

    <!-- 骨架屏：加载时 4 张卡片形状占位（loading 状态表达，reduced-motion 全局降级） -->
    <div v-if="loading" class="list">
      <div v-for="i in 4" :key="i" class="sk-card">
        <div class="sk-thumb"></div>
        <div class="sk-info">
          <div class="sk-line w50"></div>
          <div class="sk-line w30"></div>
          <div class="sk-line w90"></div>
          <div class="sk-line w40"></div>
        </div>
      </div>
    </div>

    <!-- 物料卡片：仪器角标 + 缩略图 + 等级徽标 + 库存状态 -->
    <div v-else class="list">
      <article
        v-for="m in filtered"
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
            <span :class="['level-badge', 'lv-' + m.access_level]">{{ LEVEL_TEXT[m.access_level] || m.access_level }}</span>
          </div>
          <div class="meta"><span class="lx-num">{{ m.material_id }}</span> · {{ m.model || '无型号' }} · {{ m.category }}</div>
          <div class="desc">{{ m.description }}</div>
          <div class="foot">
            <span class="location">{{ m.location }}</span>
            <span :class="['stock', 'lx-num', { empty: m.available_quantity === 0 }]">
              {{ m.available_quantity === 0 ? '借空' : `可借 ${m.available_quantity}/${m.total_quantity}` }}
            </span>
          </div>
        </div>
      </article>
      <el-empty v-if="filtered.length === 0" description="没有匹配的物料">
        <el-button @click="clearFilters">清除筛选条件</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
/* 工具栏：搜索框 + 计数读数并排 */
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--lx-space-3);
}
.search {
  max-width: 560px;
  flex: 1;
}
.count {
  flex-shrink: 0;
  font-size: var(--lx-text-sm);
  letter-spacing: 0.1em;
  color: var(--lx-text-placeholder);
}

/* 分类 chips：细边框胶囊，激活染主绿 */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--lx-space-2);
  margin-top: var(--lx-space-3);
}
.chip {
  padding: 2px var(--lx-space-3);
  font-size: var(--lx-text-xs);
  letter-spacing: 0.04em;
  color: var(--lx-text-secondary);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-pill);
  cursor: pointer;
  transition:
    color var(--lx-duration-fast) var(--lx-ease-out),
    background-color var(--lx-duration-fast) var(--lx-ease-out),
    border-color var(--lx-duration-fast) var(--lx-ease-out);
}
.chip:hover {
  color: var(--lx-text-primary);
  border-color: var(--lx-border-strong);
}
.chip.active {
  color: var(--lx-green);
  background: var(--lx-green-light-9);
  border-color: var(--lx-green-light-7);
  font-weight: var(--lx-font-medium);
}

.list {
  margin-top: var(--lx-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
}

/* 物料卡片：细边框分组，hover 微抬升 + 角标染绿 */
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
  border-color: var(--lx-green-light-5);
}

.thumb {
  width: 72px;
  height: 72px;
  border-radius: var(--lx-radius-sm);
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--lx-space-2);
}
.name {
  font-size: var(--lx-text-md);
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-primary);
  line-height: var(--lx-leading-tight);
}
/* 等级徽标：纯中文 + 三级色，小圆角细边框 */
.level-badge {
  flex-shrink: 0;
  padding: 0 var(--lx-space-2);
  border: 1px solid;
  border-radius: 3px;
  font-size: var(--lx-text-xs);
  line-height: 1.6;
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
  font-size: var(--lx-text-xs);
  margin-top: var(--lx-space-1);
}
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
.loc-tag {
  letter-spacing: 0.08em;
  color: var(--lx-text-placeholder);
  margin-right: var(--lx-space-1);
}
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

/* 骨架屏：卡片形状占位 + 慢速呼吸（loading 状态表达） */
.sk-card {
  display: flex;
  gap: var(--lx-space-3);
  padding: var(--lx-space-3);
  background: var(--lx-bg-surface);
  border: 1px solid var(--lx-border-light);
  border-radius: var(--lx-radius-md);
  animation: sk-pulse 1.6s var(--lx-ease-standard) infinite;
}
.sk-thumb {
  width: 72px;
  height: 72px;
  border-radius: var(--lx-radius-sm);
  background: var(--lx-skeleton-base);
  flex-shrink: 0;
}
.sk-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--lx-space-2);
}
.sk-line {
  height: 12px;
  border-radius: 3px;
  background: var(--lx-skeleton-base);
}
.sk-line.w50 { width: 50%; }
.sk-line.w30 { width: 30%; }
.sk-line.w90 { width: 90%; }
.sk-line.w40 { width: 40%; }
@keyframes sk-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

@media (max-width: 480px) {
  .thumb {
    width: 64px;
    height: 64px;
  }
  .sk-thumb {
    width: 64px;
    height: 64px;
  }
}
</style>

<script setup>
import { computed, ref, watch } from 'vue'

// 物料图片：约定路径 /images/materials/{material_id}.png（存 frontend/public/images/materials/）。
// 图片可能还没生成完：加载失败时降级为占位块（浅色底 + 名称首字符大字），绝不显示破图图标。
// 尺寸/圆角由父组件通过 class 控制（如列表 .thumb 72px 方图、详情 .hero 4:3 头图）。
// 占位大字字号可用 CSS 变量 --mimg-fs 覆盖。
const props = defineProps({
  materialId: { type: String, required: true },
  name: { type: String, default: '' },
  fit: { type: String, default: 'cover' }, // cover=列表缩略图裁切；contain=详情头图完整展示
})

const failed = ref(false)
const src = computed(() => `/images/materials/${props.materialId}.png`)

// 同一个组件切换到另一件物料时，重置失败态重新尝试加载
watch(
  () => props.materialId,
  () => {
    failed.value = false
  }
)
</script>

<template>
  <div class="mimg">
    <img v-if="!failed" :src="src" :alt="name" loading="lazy" :style="{ objectFit: fit }" @error="failed = true" />
    <span v-else class="fallback" aria-hidden="true">{{ (name || '?').slice(0, 1) }}</span>
  </div>
</template>

<style scoped>
/* 容器尺寸由父组件 class 决定，这里只负责底色、居中与裁切 */
.mimg {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--lx-bg-subtle);
}
.mimg img {
  width: 100%;
  height: 100%;
  display: block;
}
.fallback {
  font-size: var(--mimg-fs, var(--lx-text-xl));
  font-weight: var(--lx-font-semibold);
  color: var(--lx-text-placeholder);
  user-select: none;
}
</style>

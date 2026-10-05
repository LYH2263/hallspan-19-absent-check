<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>(null)
const error = ref('')
onMounted(async () => {
  try { s.value = await api('/seating/stats?hall_id=1') }
  catch (e: any) { error.value = String(e?.message || e) }
})
</script>
<template>
  <h1>统计</h1>
  <p class="sub">排座占用、缺考与违规汇总 · 与核对册共用当前有效方案</p>
  <div v-if="error" class="card">
    <strong>尚无有效方案</strong>
    <p class="muted" style="margin:0.35rem 0 0">请先到「排座图」执行排座；打开统计不会临时生成方案。</p>
  </div>
  <template v-else-if="s">
    <div class="muted" style="margin-bottom:0.5rem;font-size:0.78rem">当前有效方案 #{{ s.plan_id }}</div>
    <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
      <div><div class="muted">已到（已排座）</div><div class="stat">{{ s.seated }}</div></div>
      <div><div class="muted">缺考</div>
        <div class="stat">{{ s.absent ?? 0 }}</div>
        <div v-if="s.reserve_absent_seat" class="muted" style="font-size:0.72rem">占格 {{ s.absent_held ?? 0 }}</div>
      </div>
      <div><div class="muted">未排上</div><div class="stat">{{ s.unplaced }}</div></div>
      <div><div class="muted">违规数</div><div class="stat">{{ s.violations }}</div></div>
      <div><div class="muted">占格 / 容量</div><div class="stat">{{ s.occupied }} / {{ s.capacity }}</div></div>
      <div><div class="muted">名册合计</div><div class="stat">{{ s.roster_total }}</div></div>
    </div>
  </template>
  <div v-else class="card"><span class="muted">加载中…</span></div>
</template>

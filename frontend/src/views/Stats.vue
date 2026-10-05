<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>(null)
const noPlan = ref(false)
onMounted(async () => {
  try { s.value = await api('/seating/stats?hall_id=1'); noPlan.value = false }
  catch { s.value = null; noPlan.value = true }
})
</script>
<template>
  <h1>统计</h1>
  <p class="sub">排座占用与违规汇总 · 与排座图、违规、核对册同属当前有效方案</p>
  <div v-if="noPlan" class="card muted">尚无有效排座方案，请先在「排座图」执行排座。</div>
  <template v-else-if="s">
    <div class="card"><span class="muted">当前有效方案 #</span><strong>{{ s.plan_id }}</strong>
      <span class="muted" style="margin-left:1rem">08 策略：{{ s.strategy === 'retain' ? '缺考占格保留' : '缺考释放' }}</span>
    </div>
    <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1rem">
      <div><div class="muted">已到</div><div class="stat">{{ s.seated }}</div></div>
      <div><div class="muted">缺考</div><div class="stat">{{ s.absent }}</div></div>
      <div><div class="muted">未排上</div><div class="stat">{{ s.unplaced }}</div></div>
      <div><div class="muted">占格</div><div class="stat">{{ s.occupied }}</div></div>
      <div><div class="muted">违规数</div><div class="stat">{{ s.violations }}</div></div>
      <div><div class="muted">座位容量</div><div class="stat">{{ s.capacity }}</div></div>
    </div>
  </template>
</template>

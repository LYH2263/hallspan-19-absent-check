<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const candidates = ref<any[]>([])
const violKeys = ref<Set<string>>(new Set())
const loadError = ref('')

async function applyViolations() {
  try {
    const v = await api('/seating/violations?hall_id=1')
    const keys = new Set<string>()
    for (const x of v.violations || []) {
      if (x.a_id != null) keys.add(String(x.a_id))
      if (x.b_id != null) keys.add(String(x.b_id))
    }
    violKeys.value = keys
  } catch { violKeys.value = new Set() }
}

async function loadCurrent() {
  // 打开排座图只读取当前有效方案，不私自新增方案；需重排请点按钮。
  loadError.value = ''
  try {
    data.value = await api('/seating/latest?hall_id=1')
    await applyViolations()
  } catch (e: any) {
    data.value = null
    loadError.value = String(e?.message || e)
  }
}

async function run() {
  data.value = await api('/seating/run?hall_id=1', { method: 'POST' })
  await applyViolations()
  loadError.value = ''
}

onMounted(async () => {
  candidates.value = await api('/candidates')
  await loadCurrent()
})
const gridStyle = computed(() => data.value ? ({ gridTemplateColumns: `repeat(${data.value.cols}, 72px)` }) : {})
const cells = computed(() => {
  if (!data.value) return []
  const map = new Map<string, any>()
  for (const a of data.value.assignments || []) map.set(a.row + ',' + a.col, a)
  const out: any[] = []
  for (let r = 0; r < data.value.rows; r++) {
    for (let c = 0; c < data.value.cols; c++) {
      out.push(map.get(r + ',' + c))
    }
  }
  return out
})
function isViol(cell: any) {
  if (!cell || cell.empty || cell.absent) return false
  const id = cell.candidate_id ?? cell.id
  return id != null && violKeys.value.has(String(id))
}
function paperClass(pid: number) {
  return pid % 2 === 0 ? 'b' : 'a'
}
</script>
<template>
  <h1>考场课桌网格</h1>
  <p class="sub">课桌网格为主视图 · 左侧考生名册夹板 · 违规课桌高亮 · 与核对册/统计共用当前有效方案</p>
  <button class="btn" @click="run">重新排座（生成并切换到新方案）</button>
  <div v-if="data" class="muted" style="margin:0.4rem 0;font-size:0.78rem">
    当前有效方案 #{{ data.plan_id ?? data.id }}
    <span v-if="data.reserve_absent_seat">· 缺考占格保留</span>
  </div>
  <div v-if="loadError" class="card">
    <strong>尚无有效方案</strong>
    <p class="muted" style="margin:0.35rem 0 0">点击上方按钮执行排座后，排座图、违规、统计、缺考核对册将指向同一张方案。</p>
  </div>
  <div class="hs-classroom" style="margin-top:0.85rem">
    <aside class="hs-clipboard">
      <h2>考生名册</h2>
      <div v-for="c in candidates" :key="c.id" class="hs-roster-row">
        <div>
          <div>{{ c.name }}</div>
          <div class="hs-ticket">{{ c.ticket_no }}</div>
        </div>
        <div>卷{{ c.paper_id }}</div>
      </div>
    </aside>
    <div class="hs-desk-stage" v-if="data">
      <div class="hs-grid-board" :style="gridStyle">
        <div
          v-for="(cell,i) in cells" :key="i"
          class="hs-desk"
          :class="{ empty: !cell, 'hs-viol': isViol(cell), 'hs-absent': cell && cell.absent }"
        >
          <template v-if="cell && !cell.absent">
            <span class="hs-paper-tag" :class="paperClass(cell.paper_id)">卷{{ cell.paper_id }}</span>
            <div>{{ cell.name }}</div>
          </template>
          <template v-else-if="cell && cell.absent">
            <span class="hs-paper-tag" style="background:#6a7a88">缺</span>
            <div class="muted">缺考占格</div>
          </template>
          <template v-else>·</template>
        </div>
      </div>
    </div>
  </div>
</template>

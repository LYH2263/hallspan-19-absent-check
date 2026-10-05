<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const data = ref<any>(null)
const error = ref('')
const filter = ref<'all' | 'present' | 'absent' | 'unplaced'>('all')

onMounted(async () => {
  try {
    data.value = await api('/seating/roster?hall_id=1')
  } catch (e: any) {
    error.value = String(e?.message || e)
  }
})

const rows = computed(() => {
  const all: any[] = data.value?.rows || []
  return filter.value === 'all' ? all : all.filter(r => r.status === filter.value)
})

const STATUS: Record<string, { label: string; cls: string }> = {
  present: { label: '已到', cls: 'badge-ok' },
  absent: { label: '缺考', cls: 'badge-bad' },
  unplaced: { label: '未排', cls: 'badge-warn' },
}

function seat(r: any) {
  if (r.status === 'absent' && r.held) return `${r.row + 1}排${r.col + 1}座（缺考占格保留）`
  if (r.status === 'present') return `${r.row + 1}排${r.col + 1}座`
  return '—'
}
</script>

<template>
  <h1>缺考核对册</h1>
  <p class="sub">只读 · 已到 / 缺考 / 未排以当前有效方案为准，与排座图、违规、统计同一张方案</p>

  <div v-if="error" class="card">
    <strong>暂无可用核对册</strong>
    <p class="muted" style="margin:0.35rem 0 0">打开核对册不会重新排座。请先到「排座图」执行排座，或在方案作废后切换到有效方案。</p>
    <p class="muted" style="margin:0.35rem 0 0;font-size:0.75rem">{{ error }}</p>
  </div>

  <template v-else-if="data">
    <div class="card" style="display:flex;flex-wrap:wrap;gap:1rem;align-items:center;justify-content:space-between">
      <div>
        <div class="muted">考室 · 当前有效方案</div>
        <div style="font-weight:700;margin-top:0.15rem">
          {{ data.hall.name }} <span class="muted">#{{ data.plan_id }}</span>
        </div>
      </div>
      <div>
        <span class="badge" :class="data.summary.reserve_absent_seat ? 'badge-warn' : 'badge-ok'">
          缺考策略：{{ data.summary.reserve_absent_seat ? '占格保留' : '释放（不占格）' }}
        </span>
      </div>
    </div>

    <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1rem">
      <div><div class="muted">已到</div><div class="stat">{{ data.summary.present }}</div></div>
      <div>
        <div class="muted">缺考</div>
        <div class="stat">{{ data.summary.absent }}</div>
        <div v-if="data.summary.reserve_absent_seat" class="muted" style="font-size:0.72rem">
          占格 {{ data.summary.absent_held }}
        </div>
      </div>
      <div><div class="muted">未排</div><div class="stat">{{ data.summary.unplaced }}</div></div>
      <div><div class="muted">违规数</div><div class="stat">{{ data.summary.violations }}</div></div>
      <div><div class="muted">占格 / 容量</div>
        <div class="stat">{{ data.summary.occupied }} / {{ data.summary.capacity }}</div>
      </div>
      <div><div class="muted">名册合计</div><div class="stat">{{ data.summary.roster_total }}</div></div>
    </div>

    <div class="card">
      <div style="display:flex;gap:0.4rem;margin-bottom:0.6rem">
        <button class="btn" :style="filter==='all' ? {opacity:1} : {opacity:0.55}"
                @click="filter='all'">全部</button>
        <button class="btn" :style="filter==='present' ? {opacity:1} : {opacity:0.55}"
                @click="filter='present'">已到</button>
        <button class="btn" :style="filter==='absent' ? {opacity:1} : {opacity:0.55}"
                @click="filter='absent'">缺考</button>
        <button class="btn" :style="filter==='unplaced' ? {opacity:1} : {opacity:0.55}"
                @click="filter='unplaced'">未排</button>
      </div>
      <table>
        <thead>
          <tr><th>准考证号</th><th>姓名</th><th>试卷套</th><th>状态</th><th>座次</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.candidate_id">
            <td>{{ r.ticket_no }}</td>
            <td>{{ r.name }}</td>
            <td>卷{{ r.paper_id }}</td>
            <td><span class="badge" :class="STATUS[r.status].cls">{{ STATUS[r.status].label }}</span></td>
            <td>{{ seat(r) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rows.length" class="muted">无该状态记录</p>
    </div>
  </template>

  <div v-else class="card"><span class="muted">加载中…</span></div>
</template>

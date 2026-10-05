<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const reg = ref<any>(null)
const noPlan = ref(false)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    reg.value = await api('/seating/register?hall_id=1')
    noPlan.value = false
  } catch {
    reg.value = null
    noPlan.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

// 保留策略下缺考者的占格座次，键为考生 id（与排座图同一份 assignments）。
const seatById = computed<Record<number, string>>(() => {
  const m: Record<number, string> = {}
  for (const a of reg.value?.absent_seats || []) m[a.candidate_id] = `${a.row}, ${a.col}`
  return m
})

function strategyHint(s: string) {
  return s === 'retain'
    ? '缺考占格保留：缺考计入占格、不再记入未排'
    : '缺考释放：缺考不占格'
}
</script>

<template>
  <h1>缺考核对册</h1>
  <p class="sub">只读核对 · 已到 / 缺考 / 未排 与排座图、违规、统计同属当前有效方案；打开本页不会生成新方案</p>

  <div v-if="loading" class="muted">载入中…</div>

  <div v-else-if="noPlan" class="card">
    <strong>尚无有效排座方案。</strong>
    <p class="muted" style="margin-bottom:0">
      请先在「排座图」执行排座。核对册为只读，不会为凑数自行生成方案。
    </p>
  </div>

  <template v-else>
    <div class="card" style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center">
      <div><span class="muted">当前有效方案 #</span><strong>{{ reg.plan_id }}</strong></div>
      <div><span class="muted">08 策略：</span>{{ strategyHint(reg.strategy) }}</div>
    </div>

    <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1rem">
      <div><div class="muted">已到</div><div class="stat">{{ reg.counts.arrived }}</div></div>
      <div><div class="muted">缺考</div><div class="stat">{{ reg.counts.absent }}</div></div>
      <div><div class="muted">未排</div><div class="stat">{{ reg.counts.unseated }}</div></div>
      <div><div class="muted">占格</div><div class="stat">{{ reg.counts.occupied }}</div></div>
      <div><div class="muted">座位容量</div><div class="stat">{{ reg.counts.capacity }}</div></div>
    </div>

    <div class="card">
      <h3>已到 <span class="muted">（{{ reg.arrived.length }}）</span></h3>
      <table>
        <thead><tr><th>准考证号</th><th>姓名</th><th>试卷套</th><th>座次(行,列)</th></tr></thead>
        <tbody>
          <tr v-for="a in reg.arrived" :key="a.candidate_id">
            <td>{{ a.ticket_no }}</td><td>{{ a.name }}</td><td>卷{{ a.paper_id }}</td>
            <td>{{ a.row }}, {{ a.col }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!reg.arrived.length" class="muted">无</p>
    </div>

    <div class="card">
      <h3>
        缺考 <span class="muted">（{{ reg.absent.length }}）·
        <template v-if="reg.strategy==='retain'">占格保留</template><template v-else>释放不占格</template></span>
      </h3>
      <table>
        <thead>
          <tr>
            <th>准考证号</th><th>姓名</th><th>试卷套</th>
            <th v-if="reg.strategy==='retain'">占格(行,列)</th><th v-else>处理</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="x in reg.absent" :key="x.id">
            <td>{{ x.ticket_no }}</td><td>{{ x.name }}</td><td>卷{{ x.paper_id }}</td>
            <td v-if="reg.strategy==='retain'">{{ seatById[x.id] ?? '—' }}</td>
            <td v-else><span class="badge badge-warn">释放未占格</span></td>
          </tr>
        </tbody>
      </table>
      <p v-if="!reg.absent.length" class="muted">未配缺考，册上缺考为 0。</p>
    </div>

    <div class="card">
      <h3>未排 <span class="muted">（{{ reg.unseated.length }}）· 到场但未能排座</span></h3>
      <table>
        <thead><tr><th>准考证号</th><th>姓名</th><th>试卷套</th></tr></thead>
        <tbody>
          <tr v-for="u in reg.unseated" :key="u.id">
            <td>{{ u.ticket_no }}</td><td>{{ u.name }}</td><td>卷{{ u.paper_id }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!reg.unseated.length" class="muted">无</p>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const data = ref<any>(null)
const candidates = ref<any[]>([])
const plans = ref<any[]>([])
const noPlan = ref(false)
const dirtyAbsence = ref(false)

async function loadPlans() {
  plans.value = await api('/seating/plans?hall_id=1')
}

const violKeys = computed(() => {
  const keys = new Set<string>()
  for (const x of data.value?.violations || []) {
    if (x.a_id != null) keys.add(String(x.a_id))
    if (x.b_id != null) keys.add(String(x.b_id))
  }
  return keys
})

async function loadEffective() {
  try {
    data.value = await api('/seating/effective?hall_id=1')
    noPlan.value = false
  } catch {
    data.value = null
    noPlan.value = true
  }
}

async function run() {
  data.value = await api('/seating/run?hall_id=1', { method: 'POST' })
  noPlan.value = false
  dirtyAbsence.value = false
  await Promise.all([loadPlans(), refreshCandidates()])
}

async function refreshCandidates() {
  candidates.value = await api('/candidates')
}

async function toggleAbsent(c: any) {
  if (c.absent) await api(`/absentees/${c.id}`, { method: 'DELETE' })
  else await api('/absentees', { method: 'POST', body: JSON.stringify({ candidate_id: c.id }) })
  await refreshCandidates()
  dirtyAbsence.value = true
}

async function setVoid(p: any, voided: boolean) {
  await api(`/seating/${p.id}/${voided ? 'void' : 'reinstate'}`, { method: 'POST' })
  await Promise.all([loadPlans(), loadEffective()])
}

onMounted(async () => {
  await refreshCandidates()
  await Promise.all([loadEffective(), loadPlans()])
})

const gridStyle = computed(() => data.value ? ({ gridTemplateColumns: `repeat(${data.value.cols}, 72px)` }) : {})
const cells = computed(() => {
  if (!data.value) return []
  const map = new Map<string, any>()
  for (const a of data.value.assignments || []) map.set(a.row + ',' + a.col, a)
  const out: any[] = []
  for (let r = 0; r < data.value.rows; r++) {
    for (let c = 0; c < data.value.cols; c++) {
      out.push(map.get(r + ',' + c) || { empty: true, row: r, col: c })
    }
  }
  return out
})
function isViol(cell: any) {
  if (cell.empty || cell.absent) return false
  const id = cell.candidate_id ?? cell.id
  return id != null && violKeys.value.has(String(id))
}
function paperClass(pid: number) { return pid % 2 === 0 ? 'b' : 'a' }
</script>

<template>
  <h1>考场课桌网格</h1>
  <p class="sub">课桌网格为主视图 · 左侧考生名册夹板 · 违规课桌高亮 · 缺考占格按 08 策略保留</p>

  <div class="card" style="display:flex;gap:1rem;align-items:center;flex-wrap:wrap">
    <button class="btn" @click="run">{{ noPlan ? '执行排座' : '重新排座' }}</button>
    <span v-if="data" class="muted">当前有效方案 #{{ data.id }}（{{ data.hall?.absent_strategy === 'retain' ? '缺考占格保留' : '缺考释放' }}）</span>
    <span v-if="dirtyAbsence" class="badge badge-warn">缺考名单已修改，重新排座后生效</span>
  </div>

  <div class="card" v-if="noPlan">
    <strong>尚无有效排座方案。</strong>
    <span class="muted"> 点击「执行排座」生成；只读页面（如核对册）不会代为生成。</span>
  </div>

  <div class="card" v-if="plans.length">
    <h3 style="margin:0 0 0.4rem">方案与作废</h3>
    <table>
      <thead><tr><th>方案</th><th>生成时间</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="p in plans" :key="p.id">
          <td>#{{ p.id }}<span v-if="p.effective" class="badge badge-ok" style="margin-left:.4rem">当前有效</span></td>
          <td>{{ p.created_at }}</td>
          <td><span :class="p.voided ? 'badge badge-bad' : 'badge badge-ok'">{{ p.voided ? '已作废' : '有效' }}</span></td>
          <td>
            <button class="btn" v-if="!p.voided" @click="setVoid(p, true)">作废</button>
            <button class="btn" v-else @click="setVoid(p, false)">恢复</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="muted" style="margin:.4rem 0 0">作废后当前指针自动落到次新未作废方案，排座图 / 违规 / 统计 / 核对册随之跟新。</p>
  </div>

  <div class="hs-classroom" style="margin-top:0.85rem">
    <aside class="hs-clipboard">
      <h2>考生名册</h2>
      <div v-for="c in candidates" :key="c.id" class="hs-roster-row">
        <div>
          <div>{{ c.name }}</div>
          <div class="hs-ticket">{{ c.ticket_no }}</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:.2rem;align-items:flex-end">
          <div>卷{{ c.paper_id }}</div>
          <button class="btn" style="padding:.1rem .4rem;font-size:.66rem"
                  :class="c.absent ? 'badge-bad' : ''"
                  @click="toggleAbsent(c)">
            {{ c.absent ? '缺考 ✓' : '标缺考' }}
          </button>
        </div>
      </div>
    </aside>
    <div class="hs-desk-stage" v-if="data">
      <div class="hs-grid-board" :style="gridStyle">
        <div
          v-for="(cell,i) in cells" :key="i"
          class="hs-desk"
          :class="{ empty: cell.empty, 'hs-viol': isViol(cell), 'hs-absent': cell.absent }"
        >
          <template v-if="cell.absent">
            <span class="hs-paper-tag b">缺</span>
            <div>缺考占格</div>
          </template>
          <template v-else-if="!cell.empty">
            <span class="hs-paper-tag" :class="paperClass(cell.paper_id)">卷{{ cell.paper_id }}</span>
            <div>{{ cell.name }}</div>
          </template>
          <template v-else>·</template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const halls = ref<any[]>([])
const candidates = ref<any[]>([])
const plans = ref<any[]>([])
const selectedHall = ref(1)
const reserve = ref(false)
const chosenAbsent = ref<Set<number>>(new Set())
const savedTick = ref('')

const hallCandidates = computed(() =>
  candidates.value.filter(c => c.hall_id === selectedHall.value))

async function refresh() {
  const [h, c] = await Promise.all([api('/halls'), api('/candidates')])
  halls.value = h; candidates.value = c
  const cur = h.find((x: any) => x.id === selectedHall.value) || h[0]
  if (cur) {
    selectedHall.value = cur.id
    reserve.value = !!cur.reserve_absent_seat
  }
  const ab = await api(`/absences?hall_id=${selectedHall.value}`)
  chosenAbsent.value = new Set(ab.map((x: any) => x.candidate_id))
  await loadPlans()
}
async function loadPlans() {
  plans.value = await api(`/seating/plans?hall_id=${selectedHall.value}`)
}
async function pickHall(id: number) {
  selectedHall.value = id
  const cur = halls.value.find(x => x.id === id)
  reserve.value = !!cur?.reserve_absent_seat
  const ab = await api(`/absences?hall_id=${id}`)
  chosenAbsent.value = new Set(ab.map((x: any) => x.candidate_id))
  await loadPlans()
}
function toggleAbsent(id: number) {
  const next = new Set(chosenAbsent.value)
  next.has(id) ? next.delete(id) : next.add(id)
  chosenAbsent.value = next
}
async function savePolicy() {
  await api(`/halls/${selectedHall.value}`, {
    method: 'PATCH',
    body: JSON.stringify({ reserve_absent_seat: reserve.value }),
  })
  await api('/absences', {
    method: 'POST',
    body: JSON.stringify({ hall_id: selectedHall.value, candidate_ids: [...chosenAbsent.value] }),
  })
  savedTick.value = '已保存。请在「排座图」重新排座后，核对册按新口径出数。'
  await refresh()
}
async function voidPlan(id: number) {
  await api(`/seating/plans/${id}/void`, { method: 'POST' }); await loadPlans()
}
async function activatePlan(id: number) {
  await api(`/seating/plans/${id}/activate`, { method: 'POST' }); await refresh()
}

onMounted(refresh)
</script>
<template>
  <h1>考室</h1>
  <p class="sub">网格与最小曼哈顿间距 · 缺考策略（与 08 口径一致）· 方案指针切换</p>

  <div class="card">
    <strong>选择考室：</strong>
    <button v-for="r in halls" :key="r.id" class="btn"
            :style="r.id===selectedHall ? {opacity:1} : {opacity:0.55}"
            style="margin-left:0.4rem" @click="pickHall(r.id)">
      {{ r.name }}
    </button>
  </div>

  <div class="card" v-for="r in halls.filter(x=>x.id===selectedHall)" :key="r.id">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>行</th><th>列</th><th>最小间距</th></tr></thead>
      <tbody>
        <tr><td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.rows }}</td><td>{{ r.cols }}</td><td>{{ r.min_manhattan }}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h3 style="margin-top:0">缺考策略与名单</h3>
    <label style="display:flex;gap:0.5rem;align-items:center;font-weight:700">
      <input type="checkbox" :checked="reserve" @change="reserve = ($event.target as HTMLInputElement).checked">
      启用缺考占格保留
    </label>
    <p class="muted" style="margin:0.3rem 0 0.6rem;font-size:0.78rem">
      勾选：缺考计入占格、不得记入未排；不勾（释放策略）：缺考不占格、也不计未排。
    </p>
    <table>
      <thead><tr><th></th><th>准考证号</th><th>姓名</th><th>试卷套</th><th>标记缺考</th></tr></thead>
      <tbody>
        <tr v-for="c in hallCandidates" :key="c.id">
          <td></td>
          <td>{{ c.ticket_no }}</td><td>{{ c.name }}</td><td>卷{{ c.paper_id }}</td>
          <td><input type="checkbox" :checked="chosenAbsent.has(c.id)" @change="toggleAbsent(c.id)"></td>
        </tr>
      </tbody>
    </table>
    <div style="margin-top:0.6rem;display:flex;align-items:center;gap:0.8rem">
      <button class="btn" @click="savePolicy">保存配置（不自动排座）</button>
      <span class="muted" style="font-size:0.78rem">{{ savedTick }}</span>
    </div>
  </div>

  <div class="card">
    <h3 style="margin-top:0">方案与当前指针</h3>
    <table>
      <thead><tr><th>方案</th><th>生成时间</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="p in plans" :key="p.id">
          <td>#{{ p.id }}</td>
          <td>{{ p.created_at }}</td>
          <td>
            <span class="badge" :class="p.voided ? 'badge-bad' : (p.active ? 'badge-ok' : 'badge-warn')">
              {{ p.voided ? '已作废' : (p.active ? '当前有效' : '有效·未指向') }}
            </span>
          </td>
          <td>
            <button v-if="!p.voided && !p.active" class="btn" style="margin-right:0.4rem"
                    @click="activatePlan(p.id)">切换为当前</button>
            <button v-if="!p.voided" class="btn" @click="voidPlan(p.id)">作废</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!plans.length" class="muted">尚无方案，请先到「排座图」排座。</p>
  </div>
</template>

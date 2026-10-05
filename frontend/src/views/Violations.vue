<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const viols = ref<any[]>([])
const unplaced = ref<any[]>([])
const planId = ref<number | null>(null)
const noPlan = ref(false)
onMounted(async () => {
  try {
    const res = await api('/seating/violations?hall_id=1')
    viols.value = res.violations; unplaced.value = res.unplaced; planId.value = res.plan_id
    noPlan.value = false
  } catch {
    viols.value = []; unplaced.value = []; planId.value = null; noPlan.value = true
  }
})
</script>
<template>
  <h1>违规</h1>
  <p class="sub">间距不足或同试卷四邻相邻 · 取自当前有效方案</p>
  <div v-if="noPlan" class="card muted">尚无有效排座方案，请先在「排座图」执行排座。</div>
  <template v-else>
    <div class="card muted">当前有效方案 #{{ planId }}</div>
    <div class="card">
      <table>
        <thead><tr><th>类型</th><th>考生A</th><th>考生B</th><th>说明</th></tr></thead>
        <tbody>
          <tr v-for="(v,i) in viols" :key="i">
            <td>{{ v.kind }}</td><td>{{ v.a_id }}</td><td>{{ v.b_id }}</td><td>{{ v.detail }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!viols.length" class="muted">无违规</p>
    </div>
    <div class="card" v-if="unplaced.length">
      <h3>未排上</h3>
      <div v-for="u in unplaced" :key="u.id">{{ u.name }}（{{ u.ticket_no }}）</div>
    </div>
  </template>
</template>

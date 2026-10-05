<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
async function load() { rows.value = await api('/halls') }
onMounted(load)
async function toggleStrategy(r: any) {
  const next = r.absent_strategy === 'retain' ? 'release' : 'retain'
  await api(`/halls/${r.id}/strategy`, {
    method: 'PATCH',
    body: JSON.stringify({ absent_strategy: next }),
  })
  await load()
}
</script>
<template>
  <h1>考室</h1>
  <p class="sub">考室网格、最小曼哈顿间距与缺考占格策略（08 策略）</p>
  <div class="card">
    <table>
      <thead>
        <tr><th>编码</th><th>名称</th><th>行</th><th>列</th><th>最小间距</th><th>缺考占格策略</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.rows }}</td><td>{{ r.cols }}</td>
          <td>{{ r.min_manhattan }}</td>
          <td>
            <span :class="r.absent_strategy === 'retain' ? 'badge badge-ok' : 'badge badge-warn'">
              {{ r.absent_strategy === 'retain' ? '占格保留' : '释放不占格' }}
            </span>
          </td>
          <td><button class="btn" @click="toggleStrategy(r)">切换策略</button></td>
        </tr>
      </tbody>
    </table>
    <p class="muted" style="margin:.5rem 0 0">
      占格保留：缺考计入占格、不再记入未排；释放：缺考不占格。切换后在排座图重新执行排座方按新口径生效。
    </p>
  </div>
</template>

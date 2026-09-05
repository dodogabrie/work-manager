<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import DayList from '../components/DayList.vue'
import ProposalBar from '../components/ProposalBar.vue'
import QuickAdd from '../components/QuickAdd.vue'
import StatBar from '../components/StatBar.vue'
import TaskQueue from '../components/TaskQueue.vue'
import WeekCalendar from '../components/WeekCalendar.vue'
import { useBreakpoint } from '../composables/useBreakpoint'
import { usePlanningStore } from '../stores/planning'

/* §32.4.1: una schermata sola copre il 90% del lavoro quotidiano.
   Desktop: split Coda | Planning. Mobile: due tab a piena larghezza con swipe,
   perché lo split compresso non è leggibile su un telefono. */
const store = usePlanningStore()
const { grid, desktop } = useBreakpoint()

const tab = ref<'queue' | 'plan'>('queue')

/* Quando un riordino genera un'anteprima, la tab Piano lo segnala. */
watch(() => store.hasProposal, (now) => { if (now && !desktop.value) badge.value = true })
const badge = ref(false)
watch(tab, (t) => { if (t === 'plan') badge.value = false })

let startX = 0
let startY = 0
function onTouchStart(e: TouchEvent) {
  startX = e.changedTouches[0].clientX
  startY = e.changedTouches[0].clientY
}
function onTouchEnd(e: TouchEvent) {
  const dx = e.changedTouches[0].clientX - startX
  const dy = e.changedTouches[0].clientY - startY
  if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return
  tab.value = dx < 0 ? 'plan' : 'queue'
}

onMounted(() => store.load())
</script>

<template>
  <div class="planning">
    <StatBar />

    <p v-if="store.error && !store.hasProposal" class="banner" role="alert">{{ store.error }}</p>

    <!-- Desktop: coda a sinistra, planning a destra. -->
    <div v-if="desktop" class="split">
      <div class="pane left"><TaskQueue /></div>
      <div class="pane right"><WeekCalendar /></div>
    </div>

    <!-- Mobile e tablet: due tab a piena larghezza. -->
    <template v-else>
      <div class="tabs" role="tablist" aria-label="Coda e piano">
        <button
          role="tab" :aria-selected="tab === 'queue'" :class="{ on: tab === 'queue' }"
          @click="tab = 'queue'"
        >Coda</button>
        <button
          role="tab" :aria-selected="tab === 'plan'" :class="{ on: tab === 'plan' }"
          @click="tab = 'plan'"
        >
          Piano
          <span v-if="badge" class="badge">anteprima</span>
        </button>
      </div>
      <div class="pane" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
        <TaskQueue v-show="tab === 'queue'" />
        <div v-show="tab === 'plan'">
          <WeekCalendar v-if="grid" />
          <DayList v-else />
        </div>
      </div>
    </template>

    <ProposalBar />
    <QuickAdd />
  </div>
</template>

<style scoped>
.planning { display: flex; flex-direction: column; min-height: 100%; padding-bottom: 8px; }
.pane { flex: 1; min-height: 0; overflow-y: auto; }

.banner {
  margin: 0 12px 8px; padding: 8px 10px; border-radius: var(--radius);
  background: var(--danger-soft); color: var(--danger); font-size: 13px;
}

.tabs { display: flex; gap: 0; padding: 0 12px; border-bottom: 1px solid var(--border); }
.tabs button {
  flex: 1; border: none; background: none; border-radius: 0;
  border-bottom: 2px solid transparent; color: var(--text-dim);
}
.tabs button.on { color: var(--text); border-bottom-color: var(--accent); font-weight: 600; }
.badge {
  margin-left: 6px; padding: 1px 6px; border-radius: 999px;
  font-size: 10px; background: var(--accent-soft); color: var(--accent);
}

@media (min-width: 1024px) {
  .split { flex: 1; display: grid; grid-template-columns: minmax(300px, 380px) 1fr; gap: 12px; min-height: 0; padding: 0 12px; }
  .left { border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); }
  .right { min-width: 0; }
}
</style>

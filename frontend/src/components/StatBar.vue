<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { usePlanningStore } from '../stores/planning'
import { hm, longDay } from '../util/time'

/* §32.4.1: pochi indicatori sintetici, niente dashboard separata. */
const store = usePlanningStore()
</script>

<template>
  <div class="stats">
    <div class="stat">
      <span class="k">Oggi</span>
      <span class="v">
        {{ hm(store.todayCapacity.planned_minutes) }}/{{ hm(store.todayCapacity.available_minutes) }}
        <span class="unit">pianificate</span>
      </span>
    </div>
    <div class="stat">
      <span class="k">Prossima consegna</span>
      <span class="v" v-if="store.nextDelivery">
        {{ store.nextDelivery.title }} <span class="unit">{{ longDay(store.nextDelivery.day) }}</span>
      </span>
      <span class="v unit" v-else>nessuna</span>
    </div>
    <RouterLink class="stat link" to="/inbox">
      <span class="k">Inbox</span>
      <span class="v">{{ store.inbox.length }} <span class="unit">element{{ store.inbox.length === 1 ? 'o' : 'i' }}</span></span>
    </RouterLink>
  </div>
</template>

<style scoped>
.stats {
  display: flex; gap: 8px;
  padding: 8px 12px;
  overflow-x: auto;
}
.stat {
  flex: 1 0 auto; min-width: 0;
  display: flex; flex-direction: column; gap: 2px;
  padding: 6px 10px;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  text-decoration: none; color: inherit;
}
.link:hover { border-color: var(--accent); }
.k { font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-dim); }
.v { font-size: 14px; font-weight: 500; white-space: nowrap; }
.unit { font-weight: 400; color: var(--text-dim); font-size: 12px; }
</style>

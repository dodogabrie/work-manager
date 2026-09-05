<script setup lang="ts">
import { usePlanningStore } from '../stores/planning'
import { longDay } from '../util/time'
import DayColumn from './DayColumn.vue'

/* Griglia settimanale: solo da 768px in su. Sotto, DayList. */
const store = usePlanningStore()
</script>

<template>
  <section class="week" aria-labelledby="week-heading">
    <header class="head">
      <h2 id="week-heading">
        Settimana <span class="range">{{ longDay(store.rangeStart) }} – {{ longDay(store.rangeEnd) }}</span>
      </h2>
      <div class="nav">
        <button @click="store.setWeek(-1)" aria-label="Settimana precedente">‹</button>
        <button @click="store.goToday()">Oggi</button>
        <button @click="store.setWeek(1)" aria-label="Settimana successiva">›</button>
      </div>
    </header>
    <div class="grid">
      <DayColumn v-for="day in store.calendar" :key="day.day" :day="day" />
    </div>
  </section>
</template>

<style scoped>
.week { display: flex; flex-direction: column; min-height: 0; }
.head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px; padding: 8px 12px; flex-wrap: wrap;
}
h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .06em; margin: 0; color: var(--text-dim); }
.range { text-transform: none; letter-spacing: 0; }
.nav { display: flex; gap: 4px; }
.nav button { min-width: var(--tap); padding: 0 12px; }
.grid {
  display: grid;
  /* 96px: sette giorni entrano in un desktop normale senza scroll orizzontale,
     e sotto quella soglia il contenitore scrolla per conto suo. */
  grid-template-columns: repeat(7, minmax(96px, 1fr));
  gap: 8px;
  padding: 0 12px 12px;
  overflow-x: auto;
  align-items: start;
}
</style>

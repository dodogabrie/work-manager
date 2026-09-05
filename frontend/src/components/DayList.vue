<script setup lang="ts">
import { usePlanningStore } from '../stores/planning'
import DayColumn from './DayColumn.vue'
import { longDay } from '../util/time'

/* Mobile: il calendario è una lista verticale per giorno. Una griglia a sette
   colonne su 360px non è leggibile, quindi qui non esiste. */
const store = usePlanningStore()
</script>

<template>
  <section class="days" aria-labelledby="days-heading">
    <header class="head">
      <h2 id="days-heading">{{ longDay(store.rangeStart) }} – {{ longDay(store.rangeEnd) }}</h2>
      <div class="nav">
        <button @click="store.setWeek(-1)" aria-label="Settimana precedente">‹</button>
        <button @click="store.goToday()">Oggi</button>
        <button @click="store.setWeek(1)" aria-label="Settimana successiva">›</button>
      </div>
    </header>
    <div class="list">
      <DayColumn v-for="day in store.calendar" :key="day.day" :day="day" />
    </div>
  </section>
</template>

<style scoped>
.days { display: flex; flex-direction: column; min-height: 0; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 12px; }
h2 { font-size: 13px; margin: 0; color: var(--text-dim); }
.nav { display: flex; gap: 4px; }
.nav button { min-width: var(--tap); padding: 0 12px; }
.list { display: flex; flex-direction: column; gap: 8px; padding: 0 12px 12px; }
</style>

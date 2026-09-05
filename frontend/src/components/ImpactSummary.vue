<script setup lang="ts">
import { usePlanningStore } from '../stores/planning'
import { longDay } from '../util/time'

/* §13: piano attuale vs proposto, task spostati, vecchie e nuove date. */
const store = usePlanningStore()
</script>

<template>
  <div class="impact">
    <p v-if="!store.proposal?.simulation.changes.length" class="none">
      Nessun task cambia data.
    </p>
    <table v-else>
      <caption class="visually-hidden">Task spostati dalla modifica proposta</caption>
      <thead>
        <tr><th scope="col">Task</th><th scope="col">Prima</th><th scope="col">Dopo</th><th scope="col">Δ</th></tr>
      </thead>
      <tbody>
        <tr v-for="c in store.proposal!.simulation.changes" :key="c.task_id">
          <td>{{ store.taskById.get(c.task_id)?.title ?? c.task_id.slice(0, 8) }}</td>
          <td>{{ c.old_delivery ? longDay(c.old_delivery) : '—' }}</td>
          <td>{{ c.new_delivery ? longDay(c.new_delivery) : '—' }}</td>
          <td :class="{ late: c.shift_days > 0, early: c.shift_days < 0 }">
            {{ c.shift_days > 0 ? '+' : '' }}{{ c.shift_days }}g
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.impact { overflow-x: auto; }
.none { margin: 0; color: var(--text-dim); font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 4px 8px 4px 0; border-bottom: 1px solid var(--border); }
th { font-size: 11px; text-transform: uppercase; color: var(--text-dim); font-weight: 500; }
.late { color: var(--danger); }
.early { color: var(--accent); }
</style>

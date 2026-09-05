<script setup lang="ts">
import { ref } from 'vue'

import { useProposalStore } from '../stores/proposals'
import { longDay } from '../util/time'

/* §19.1: motivo, before/after, warning, conflitti, approve, reject — la stessa
   barra della schermata Planning, ma alimentata dallo store `proposals` invece
   che da `planning`.

   ProposalBar.vue non è riusabile qui: legge direttamente usePlanningStore e
   ne usa la coda in anteprima. Estrarne una versione a props avrebbe voluto
   dire riscrivere anche ProposalBar, che è già in uso in un altro flusso. */
const store = useProposalStore()
const emit = defineEmits<{ applied: []; discarded: [] }>()

const expanded = ref(false)

async function approve() {
  if (await store.approve()) emit('applied')
}
async function discard() {
  await store.reject()
  emit('discarded')
}
</script>

<template>
  <div v-if="store.pending" class="bar" role="region" aria-label="Modifica proposta">
    <div class="line" aria-live="polite">
      <div class="text">
        <strong>Il piano cambia</strong>
        <span class="summary">{{ store.impact }}</span>
      </div>
      <div class="actions">
        <button @click="discard()" :disabled="store.busy">Annulla</button>
        <button
          v-if="store.stale"
          class="primary"
          @click="store.recalculate()"
          :disabled="store.busy"
        >Ricalcola</button>
        <button
          v-else
          class="primary"
          @click="approve()"
          :disabled="store.busy || store.blocked"
        >Applica</button>
      </div>
    </div>

    <!-- §26. -->
    <p v-if="store.stale" class="note danger">
      <span aria-hidden="true">⚠</span>
      Il piano è cambiato nel frattempo. Ricalcola la modifica prima di applicarla.
    </p>

    <!-- §14.1: conflitto hard — non approvabile, e spiegato in chiaro. -->
    <ul v-if="store.conflicts.length" class="note danger list">
      <li v-for="(c, i) in store.conflicts" :key="i">
        <span aria-hidden="true">⛔</span> {{ c.message }}
      </li>
    </ul>

    <!-- §14.2: warning — si mostrano ma non bloccano. -->
    <ul v-if="store.warnings.length" class="note warn list">
      <li v-for="(w, i) in store.warnings" :key="i">
        <span aria-hidden="true">⚠</span> {{ w.message }}
      </li>
    </ul>

    <button class="more" :aria-expanded="expanded" @click="expanded = !expanded">
      {{ expanded ? 'Nascondi' : 'Mostra' }} il dettaglio ({{ store.changes.length }})
    </button>

    <div v-if="expanded" class="detail">
      <p v-if="!store.changes.length" class="none">Nessun task cambia data.</p>
      <table v-else>
        <caption class="visually-hidden">Task spostati dalla modifica proposta</caption>
        <thead>
          <tr>
            <th scope="col">Task</th><th scope="col">Prima</th>
            <th scope="col">Dopo</th><th scope="col">Δ</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in store.changes" :key="c.task_id">
            <td>{{ store.titleOf(c.task_id) }}</td>
            <td>{{ c.old_delivery ? longDay(c.old_delivery) : '—' }}</td>
            <td>{{ c.new_delivery ? longDay(c.new_delivery) : '—' }}</td>
            <td :class="{ late: c.shift_days > 0, early: c.shift_days < 0 }">
              {{ c.shift_days > 0 ? '+' : '' }}{{ c.shift_days }}g
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="store.error" class="note danger" role="alert">{{ store.error }}</p>
  </div>
</template>

<style scoped>
.bar {
  position: sticky; bottom: 0; z-index: 30;
  background: var(--surface);
  border-top: 2px solid var(--accent);
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  box-shadow: 0 -6px 20px rgb(0 0 0 / 12%);
  max-height: 80dvh; overflow-y: auto;
}
.line { display: flex; flex-direction: column; gap: 8px; }
.text { display: flex; flex-direction: column; }
.summary { color: var(--text-dim); font-size: 13px; }
.actions { display: flex; gap: 8px; }
.actions button { flex: 1; }

.note { margin: 8px 0 0; font-size: 13px; border-radius: 6px; padding: 6px 8px; }
.list { list-style: none; padding-left: 8px; }
.list li { padding: 2px 0; }
.danger { background: var(--danger-soft); color: var(--danger); }
.warn { background: var(--warning-soft); color: var(--warning); }

.more {
  margin-top: 8px; min-height: 32px; padding: 0 8px;
  border: none; background: none; color: var(--text-dim); font-size: 13px;
  text-decoration: underline;
}
.detail { margin-top: 4px; overflow-x: auto; }
.none { margin: 0; color: var(--text-dim); font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 4px 8px 4px 0; border-bottom: 1px solid var(--border); }
th { font-size: 11px; text-transform: uppercase; color: var(--text-dim); font-weight: 500; }
.late { color: var(--danger); }
.early { color: var(--accent); }

@media (min-width: 1024px) {
  .line { flex-direction: row; align-items: center; justify-content: space-between; }
  .actions button { flex: none; min-width: 120px; }
}
</style>

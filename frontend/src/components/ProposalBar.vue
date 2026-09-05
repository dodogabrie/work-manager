<script setup lang="ts">
import { ref } from 'vue'

import { usePlanningStore } from '../stores/planning'
import ImpactSummary from './ImpactSummary.vue'

/* §32.4.2: una barra compatta, mai una modal. Su mobile la stessa barra è un
   bottom sheet: si trascina verso l'alto per il before/after completo, e
   [Annulla] [Applica] restano sempre sotto il pollice. */
const store = usePlanningStore()
const expanded = ref(false)

let startY = 0
function onPointerDown(e: PointerEvent) { startY = e.clientY }
function onPointerUp(e: PointerEvent) {
  const dy = startY - e.clientY
  if (dy > 30) expanded.value = true
  else if (dy < -30) expanded.value = false
}
</script>

<template>
  <div v-if="store.hasProposal" class="bar" :class="{ expanded }" role="region" aria-label="Modifica proposta">
    <button
      class="grabber"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
      @pointerdown="onPointerDown"
      @pointerup="onPointerUp"
    >
      <span class="pill" aria-hidden="true"></span>
      <span class="visually-hidden">{{ expanded ? 'Riduci' : 'Espandi' }} il dettaglio dell'impatto</span>
    </button>

    <div class="line" aria-live="polite">
      <div class="text">
        <strong>Piano modificato</strong>
        <span class="summary">{{ store.impact }}</span>
      </div>
      <div class="actions">
        <button @click="store.discard()" :disabled="store.busy">Annulla</button>
        <button
          v-if="store.stale"
          class="primary"
          @click="store.recalculate()"
          :disabled="store.busy"
        >Ricalcola</button>
        <button
          v-else
          class="primary"
          @click="store.apply()"
          :disabled="store.busy || store.blocked"
        >Applica</button>
      </div>
    </div>

    <!-- §26: la proposal è stata calcolata su un piano non più corrente. -->
    <p v-if="store.stale" class="note danger">
      <span aria-hidden="true">⚠</span>
      Il piano è cambiato nel frattempo. Ricalcola la modifica prima di applicarla.
    </p>

    <!-- §14.1: conflitto hard — non confermabile, e spiegato in chiaro. -->
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

    <div v-if="expanded" class="detail">
      <ImpactSummary />
    </div>

    <p v-if="store.error" class="note danger">{{ store.error }}</p>
  </div>
</template>

<style scoped>
.bar {
  position: sticky; bottom: 0; z-index: 30;
  background: var(--surface);
  border-top: 2px solid var(--accent);
  padding: 0 12px calc(10px + env(safe-area-inset-bottom));
  box-shadow: 0 -6px 20px rgb(0 0 0 / 12%);
  max-height: 80dvh; overflow-y: auto;
}
.grabber {
  display: block; width: 100%; min-height: 22px; height: 22px;
  border: none; background: none; padding: 0;
}
.pill { display: block; width: 40px; height: 4px; border-radius: 2px; background: var(--border); margin: 0 auto; }

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
.detail { margin-top: 10px; }

@media (min-width: 1024px) {
  .grabber { display: none; }
  .line { flex-direction: row; align-items: center; justify-content: space-between; padding-top: 10px; }
  .actions button { flex: none; min-width: 120px; }
}
</style>

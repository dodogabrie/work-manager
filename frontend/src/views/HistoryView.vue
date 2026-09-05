<script setup lang="ts">
import { onMounted, ref } from 'vue'

import ProposalPanel from '../components/ProposalPanel.vue'
import type { Action } from '../api/types'
import { entityLabels, originLabel, useHistoryStore } from '../stores/history'
import { longDay } from '../util/time'

/* §23: la history non è un log da leggere, è il posto da cui si annulla.
   §23.4 in particolare: qualsiasi azione reversibile, non solo l'ultima —
   quindi ogni riga ha i suoi bottoni e il suo esito, e le azioni non
   annullabili dicono perché invece di limitarsi a essere grigie. */
const store = useHistoryStore()
const tab = ref<'actions' | 'snapshots'>('actions')

/** L'esito che l'utente deve poter distinguere a colpo d'occhio (§23.4). */
const OUTCOME = {
  applied: { label: 'Applicato', tone: 'ok', icon: '✓' },
  proposal: { label: 'Da confermare', tone: 'warn', icon: '⧗' },
  conflict: { label: 'Conflitto', tone: 'danger', icon: '⛔' },
  impossible: { label: 'Impossibile', tone: 'danger', icon: '⊘' },
} as const

function stamp(iso: string): string {
  const d = new Date(iso)
  return `${longDay(d.toISOString().slice(0, 10))}, ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function undoTitle(action: Action): string {
  return store.undoBlockedReason(action) ?? 'Annulla questa azione'
}
function redoTitle(action: Action): string {
  return store.redoBlockedReason(action) ?? 'Riapplica questa azione'
}

onMounted(() => store.load())
</script>

<template>
  <section class="history">
    <header>
      <h1>History</h1>
      <p class="sub">
        Ogni azione significativa è registrata. Da qui si può annullare
        <strong>qualsiasi</strong> azione reversibile, non solo l'ultima.
      </p>
    </header>

    <div class="tabs" role="tablist" aria-label="History e snapshot">
      <button
        role="tab" :aria-selected="tab === 'actions'" :class="{ on: tab === 'actions' }"
        @click="tab = 'actions'"
      >Azioni ({{ store.actions.length }})</button>
      <button
        role="tab" :aria-selected="tab === 'snapshots'" :class="{ on: tab === 'snapshots' }"
        @click="tab = 'snapshots'"
      >Snapshot ({{ store.snapshots.length }})</button>
    </div>

    <p v-if="store.error" class="banner" role="alert">{{ store.error }}</p>
    <p v-if="store.loading" class="empty">Caricamento…</p>

    <!-- ------------------------------------------------------------ azioni -->
    <ul v-if="tab === 'actions' && !store.loading" class="list">
      <li v-if="!store.actions.length" class="empty">Nessuna azione registrata.</li>

      <li v-for="a in store.actions" :key="a.id" class="card item" :class="{ undone: a.undone }">
        <div class="head">
          <span class="type">{{ a.action_type }}</span>
          <span v-if="a.undone" class="tag">Annullata</span>
          <span v-if="!a.reversible" class="tag">Non reversibile</span>
        </div>

        <p class="meta">
          {{ stamp(a.created_at) }} · {{ originLabel(a.origin) }}
          <template v-if="a.actor"> · {{ a.actor }}</template>
          <template v-if="a.snapshot_id"> · tocca il piano</template>
        </p>

        <p v-if="entityLabels(a.entities).length" class="entities">
          <span v-for="(e, i) in entityLabels(a.entities)" :key="i" class="tag">{{ e }}</span>
        </p>

        <div class="acts">
          <button
            :disabled="!!store.undoBlockedReason(a) || store.busy === a.id"
            :title="undoTitle(a)"
            @click="store.undo(a)"
          >Undo</button>
          <button
            :disabled="!!store.redoBlockedReason(a) || store.busy === a.id"
            :title="redoTitle(a)"
            @click="store.redo(a)"
          >Redo</button>
        </div>

        <!-- §23.6: un bottone disabilitato senza spiegazione è un vicolo cieco. -->
        <p v-if="store.undoBlockedReason(a)" class="why">{{ store.undoBlockedReason(a) }}</p>

        <!-- §23.4: i quattro esiti, distinti e nominati. -->
        <p
          v-if="store.outcomes[a.id]"
          class="outcome"
          :class="OUTCOME[store.outcomes[a.id].status].tone"
          role="status"
        >
          <span aria-hidden="true">{{ OUTCOME[store.outcomes[a.id].status].icon }}</span>
          <strong>{{ store.outcomes[a.id].verb === 'undo' ? 'Undo' : 'Redo' }}:
            {{ OUTCOME[store.outcomes[a.id].status].label }}</strong>
          <span v-if="store.outcomes[a.id].message"> — {{ store.outcomes[a.id].message }}</span>
          <span v-else-if="store.outcomes[a.id].status === 'proposal'">
            — il piano cambia: conferma la modifica proposta qui sotto.
          </span>
          <button class="dismiss" @click="store.clearOutcome(a.id)">Nascondi</button>
        </p>
      </li>
    </ul>

    <!-- ---------------------------------------------------------- snapshot -->
    <ul v-if="tab === 'snapshots' && !store.loading" class="list">
      <li v-if="!store.snapshots.length" class="empty">Nessuno snapshot.</li>
      <li v-for="s in store.snapshots" :key="s.id" class="card snap">
        <span class="version">v{{ s.plan_version }}</span>
        <span class="meta">{{ stamp(s.created_at) }}</span>
        <span v-if="s.note" class="note">{{ s.note }}</span>
      </li>
    </ul>

    <!-- §23.3: se l'undo tocca il piano si conferma, non si applica. -->
    <ProposalPanel @applied="store.load()" />
  </section>
</template>

<style scoped>
.history { display: flex; flex-direction: column; min-height: 100%; }
header { padding: 12px 12px 0; }
h1 { margin: 0; font-size: 20px; }
.sub { margin: 4px 0 8px; color: var(--text-dim); font-size: 13px; max-width: 60ch; }

.tabs { display: flex; padding: 0 12px; border-bottom: 1px solid var(--border); }
.tabs button {
  flex: 1; border: none; background: none; border-radius: 0;
  border-bottom: 2px solid transparent; color: var(--text-dim);
}
.tabs button.on { color: var(--text); border-bottom-color: var(--accent); font-weight: 600; }

.banner {
  margin: 8px 12px 0; padding: 8px 10px; border-radius: var(--radius);
  background: var(--danger-soft); color: var(--danger); font-size: 13px;
}
.empty { color: var(--text-dim); font-size: 13px; padding: 12px; margin: 0; list-style: none; }

.list { list-style: none; margin: 0; padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
.item { padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
.item.undone { opacity: .7; }

.head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.type { font-weight: 600; font-size: 14px; word-break: break-word; }
.meta { margin: 0; font-size: 12px; color: var(--text-dim); }
.entities { margin: 0; display: flex; flex-wrap: wrap; gap: 4px; }

.acts { display: flex; gap: 8px; }
.acts button { flex: 1; }
.why { margin: 0; font-size: 12px; color: var(--text-dim); }

.outcome {
  margin: 0; padding: 6px 8px; border-radius: 6px; font-size: 13px;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.outcome.ok { background: var(--accent-soft); color: var(--accent); }
.outcome.warn { background: var(--warning-soft); color: var(--warning); }
.outcome.danger { background: var(--danger-soft); color: var(--danger); }
.dismiss {
  margin-left: auto; min-height: 32px; padding: 0 8px;
  border: none; background: none; color: inherit; text-decoration: underline; font-size: 12px;
}

.snap { display: flex; align-items: center; gap: 10px; padding: 10px 12px; flex-wrap: wrap; }
.version { font-weight: 600; font-variant-numeric: tabular-nums; }
.note { font-size: 12px; color: var(--text-dim); }

@media (min-width: 768px) {
  .acts button { flex: none; min-width: 100px; }
}
@media (min-width: 1024px) {
  .list { max-width: 860px; }
  .item { display: grid; grid-template-columns: 1fr auto; align-items: start; column-gap: 12px; }
  .head, .meta, .entities { grid-column: 1; }
  .acts { grid-column: 2; grid-row: 1 / span 3; }
  .why, .outcome { grid-column: 1 / -1; }
}
</style>

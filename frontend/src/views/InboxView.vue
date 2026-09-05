<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import QuickAdd from '../components/QuickAdd.vue'
import { usePlanningStore } from '../stores/planning'
import { hm } from '../util/time'

/* §32.4.3: Inbox minimale. `Pianifica` mette il task in fondo alla coda —
   passando comunque da una proposal (§3.3, R3), che si conferma dal Planning. */
const store = usePlanningStore()
const router = useRouter()
const working = ref('')
const open = ref(new Set<string>())

function toggle(id: string) {
  const next = new Set(open.value)
  next.has(id) ? next.delete(id) : next.add(id)
  open.value = next
}

async function discard(task: { id: string; title: string }) {
  // Un'eliminazione è irreversibile per chi guarda, anche se sotto è un soft
  // delete: vale una conferma, e la conferma nomina il task.
  if (!confirm(`Eliminare «${task.title}» dall'Inbox?`)) return
  working.value = task.id
  try { await store.discardFromInbox(task.id) } finally { working.value = '' }
}

onMounted(() => { if (!store.inbox.length) void store.load() })

async function plan(id: string) {
  working.value = id
  try {
    await store.planFromInbox(id)
    await router.push('/planning')
  } catch {
    // store.error mostra il motivo, l'utente resta in Inbox.
  } finally {
    working.value = ''
  }
}
</script>

<template>
  <section class="inbox">
    <header class="head">
      <h1>Inbox</h1>
      <span class="count">{{ store.inbox.length }}</span>
    </header>

    <p v-if="store.error" class="banner" role="alert">{{ store.error }}</p>

    <p v-if="!store.inbox.length && !store.loading" class="empty">
      Niente da smistare. Usa <span aria-hidden="true">＋</span> per buttare giù una richiesta.
    </p>

    <ul class="rows">
      <li v-for="task in store.inbox" :key="task.id" class="row">
        <span class="body">
          <span class="title">{{ task.title }}</span>
          <span class="meta">
            <span v-if="task.project_id && store.projectById.get(task.project_id)" class="tag">
              <span
                class="dot"
                :style="{ background: store.projectById.get(task.project_id)!.color }"
                aria-hidden="true"
              ></span>
              {{ store.projectById.get(task.project_id)!.name }}
            </span>
            <span class="tag">{{ hm(task.planning_effort_minutes) }}</span>
          </span>
        </span>
        <span class="acts">
          <button
            v-if="task.description"
            class="expand"
            :aria-expanded="open.has(task.id)"
            :aria-controls="`inbox-desc-${task.id}`"
            :title="open.has(task.id) ? 'Nascondi la descrizione' : 'Mostra la descrizione'"
            @click="toggle(task.id)"
          >
            <span aria-hidden="true">{{ open.has(task.id) ? '⌄' : '›' }}</span>
            <span class="visually-hidden">Descrizione di {{ task.title }}</span>
          </button>
          <button
            class="drop"
            :disabled="working === task.id || store.busy"
            :aria-label="`Elimina ${task.title}`"
            @click="discard(task)"
          >Elimina</button>
          <button class="primary" :disabled="working === task.id || store.busy" @click="plan(task.id)">
            Pianifica
          </button>
        </span>

        <p v-if="open.has(task.id) && task.description" :id="`inbox-desc-${task.id}`" class="desc">
          {{ task.description }}
        </p>
      </li>
    </ul>

    <QuickAdd />
  </section>
</template>

<style scoped>
.inbox { padding: 12px 12px 24px; }
.head { display: flex; align-items: baseline; gap: 8px; }
h1 { font-size: 20px; margin: 0 0 8px; }
.count { color: var(--text-dim); font-size: 13px; }
.banner { margin: 0 0 8px; padding: 8px 10px; border-radius: var(--radius); background: var(--danger-soft); color: var(--danger); font-size: 13px; }
.empty { color: var(--text-dim); }
.rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  padding: 8px 10px; min-height: var(--tap);
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
}
.body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.title { overflow-wrap: anywhere; }
.meta { display: flex; flex-wrap: wrap; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.acts { display: flex; align-items: center; gap: 6px; }

/* Su schermo stretto i bottoni scendono su una riga propria: altrimenti
   comprimono il titolo a metà larghezza e una richiesta lunga diventa una
   colonna di due parole. */
@media (max-width: 560px) {
  .acts { flex-basis: 100%; justify-content: flex-end; }
  .body { flex-basis: 100%; }
}
.expand {
  min-height: 32px; min-width: 32px; padding: 0;
  border: none; background: none; color: var(--text-dim); font-size: 15px; line-height: 1;
}
.drop { color: var(--danger); border-color: var(--border); }
.desc {
  flex-basis: 100%;
  margin: 4px 0 0; padding: 8px 10px;
  border-radius: var(--radius); background: var(--surface-2);
  font-size: 13px; line-height: 1.5;
  white-space: pre-wrap; overflow-wrap: anywhere;
}
</style>

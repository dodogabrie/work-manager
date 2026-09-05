<script setup lang="ts">
import { computed, ref } from 'vue'
import draggable from 'vuedraggable'

import type { Task } from '../api/types'
import { usePlanningStore } from '../stores/planning'
import QueueRow from './QueueRow.vue'

/* §32.4.1: la coda è la fonte di verità dell'ordine. Il drag esprime solo
   un'intenzione: chi la trasforma in proposal è lo store. */
const store = usePlanningStore()

const list = computed({
  get: () => store.queue,
  set: (value: Task[]) => { store.queue = value },
})

/** Chi ha appena cambiato posizione: SortableJS ci dà l'indice, non l'oggetto. */
function onEnd(event: { oldIndex?: number; newIndex?: number }) {
  if (event.oldIndex === undefined || event.newIndex === undefined) return
  if (event.oldIndex === event.newIndex) return
  const task = store.queue[event.newIndex]
  if (task) void store.reorder(task.id, [...store.queue])
}

const pending = ref<Task | null>(null)   // task in attesa di "Sposta dopo…"
const anchorId = ref('')

function confirmAfter() {
  const task = pending.value
  if (!task) return
  const target = store.queue.findIndex((t) => t.id === anchorId.value)
  pending.value = null
  if (target < 0) return
  const from = store.queue.findIndex((t) => t.id === task.id)
  void store.moveTo(task.id, from < target ? target : target + 1)
}
</script>

<template>
  <section class="queue" aria-labelledby="queue-heading">
    <header class="head">
      <h2 id="queue-heading">Coda</h2>
      <span class="count">{{ store.queue.length }} task</span>
    </header>

    <div v-if="pending" class="after-picker card">
      <label :for="'after-' + pending.id">Sposta «{{ pending.title }}» dopo</label>
      <select :id="'after-' + pending.id" v-model="anchorId">
        <option value="">— inizio coda —</option>
        <option v-for="t in store.queue.filter((x) => x.id !== pending!.id)" :key="t.id" :value="t.id">
          {{ t.title }}
        </option>
      </select>
      <div class="picker-actions">
        <button @click="pending = null">Annulla</button>
        <button class="primary" @click="confirmAfter">Sposta</button>
      </div>
    </div>

    <p v-if="!store.queue.length" class="empty">
      La coda è vuota. Pianifica un task dall'Inbox per iniziare.
    </p>

    <draggable
      v-else
      v-model="list"
      item-key="id"
      tag="ul"
      class="rows"
      :delay="200"
      :delay-on-touch-only="true"
      :touch-start-threshold="6"
      :scroll-sensitivity="80"
      :force-fallback="true"
      ghost-class="ghost"
      @end="onEnd"
    >
      <template #item="{ element, index }">
        <QueueRow
          :task="element"
          :index="index"
          :total="store.queue.length"
          :project="element.project_id ? store.projectById.get(element.project_id) ?? null : null"
          :delivery="store.confirmedDeliveries.get(element.id) ?? null"
          :moved="store.movedTaskIds?.has?.(element.id) ?? false"
          @move="(target: number) => store.moveTo(element.id, target)"
          @move-after="pending = element; anchorId = ''"
        />
      </template>
    </draggable>
  </section>
</template>

<style scoped>
.queue { display: flex; flex-direction: column; min-height: 0; }
.head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 8px; padding: 8px 12px;
}
h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .06em; margin: 0; color: var(--text-dim); }
.count { font-size: 12px; color: var(--text-dim); }
.rows { list-style: none; margin: 0; padding: 0; overflow-y: auto; }
.empty { padding: 24px 16px; color: var(--text-dim); }
.ghost { opacity: .4; }
.after-picker { margin: 0 12px 8px; padding: 10px; display: grid; gap: 8px; }
.after-picker label { font-size: 13px; color: var(--text-dim); }
.picker-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>

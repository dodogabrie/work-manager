<script setup lang="ts">
import { ref } from 'vue'

import type { Task } from '../api/types'
import { hm, longDay } from '../util/time'

/* Una riga della coda. Il colore del progetto non è mai solo colore: accanto
   c'è sempre il nome (§32.4 / accessibilità). */
const props = defineProps<{
  task: Task
  index: number
  total: number
  project: { name: string; color: string } | null
  delivery: string | null
  moved: boolean
}>()

const emit = defineEmits<{
  (e: 'move', target: number): void
  (e: 'moveAfter'): void
}>()

const menu = ref(false)

function pick(target: number) {
  menu.value = false
  emit('move', target)
}
</script>

<template>
  <li class="row" :class="{ moved }">
    <span class="grip" aria-hidden="true">⠿</span>

    <span class="pos">{{ index + 1 }}</span>

    <span class="body">
      <span class="title">{{ task.title }}</span>
      <span class="meta">
        <span v-if="project" class="tag project">
          <span class="dot" :style="{ background: project.color }" aria-hidden="true"></span>
          {{ project.name }}
        </span>
        <span class="tag">{{ hm(task.planning_effort_minutes) }}</span>
        <span v-if="task.fixed_delivery_date" class="tag fixed">
          <span aria-hidden="true">🔒</span> Fissa {{ longDay(task.fixed_delivery_date) }}
        </span>
        <span v-else-if="task.target_delivery_date" class="tag target">
          <span aria-hidden="true">◎</span> Target {{ longDay(task.target_delivery_date) }}
        </span>
        <span v-if="delivery" class="tag">Consegna {{ longDay(delivery) }}</span>
        <span v-if="moved" class="tag moved-tag"><span aria-hidden="true">↧</span> spostato</span>
      </span>
    </span>

    <span class="menu-wrap">
      <button
        class="menu-btn"
        :aria-expanded="menu"
        :aria-label="`Azioni per ${task.title}`"
        @click="menu = !menu"
      >⋮</button>
      <!-- Alternativa al drag: indispensabile da tastiera e su liste lunghe. -->
      <ul v-if="menu" class="menu" @focusout="menu = false">
        <li><button @click="pick(0)" :disabled="index === 0">Sposta in cima</button></li>
        <li><button @click="pick(index - 1)" :disabled="index === 0">Sposta su</button></li>
        <li><button @click="pick(index + 1)" :disabled="index === total - 1">Sposta giù</button></li>
        <li><button @click="pick(total - 1)" :disabled="index === total - 1">Sposta in fondo</button></li>
        <li><button @click="menu = false; emit('moveAfter')">Sposta dopo…</button></li>
      </ul>
    </span>
  </li>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: var(--tap);
  padding: 8px 6px 8px 2px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.row.moved { background: var(--accent-soft); }
.grip { color: var(--text-dim); cursor: grab; touch-action: none; padding: 0 4px; }
.pos {
  min-width: 22px; text-align: right;
  font-variant-numeric: tabular-nums; color: var(--text-dim); font-size: 12px;
}
.body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.title { font-weight: 500; overflow-wrap: anywhere; }
.meta { display: flex; flex-wrap: wrap; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.project { background: var(--surface-2); }
.fixed { background: var(--danger-soft); color: var(--danger); }
.target { background: var(--warning-soft); color: var(--warning); }
.moved-tag { background: var(--accent-soft); color: var(--accent); }

.menu-wrap { position: relative; }
.menu-btn {
  min-width: var(--tap); min-height: var(--tap);
  padding: 0; border: none; background: none; color: var(--text-dim);
}
.menu {
  position: absolute; right: 0; top: 100%; z-index: 20;
  margin: 0; padding: 4px; list-style: none;
  min-width: 190px;
  background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius);
  box-shadow: 0 8px 24px rgb(0 0 0 / 18%);
}
.menu button {
  width: 100%; text-align: left; border: none; background: none;
  border-radius: 6px; padding: 0 10px;
}
.menu button:hover:not(:disabled) { background: var(--surface-2); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>

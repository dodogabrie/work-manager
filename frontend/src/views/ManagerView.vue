<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError, api } from '../api/client'
import type { ManagerTask } from '../api/types'
import { useBreakpoint } from '../composables/useBreakpoint'
import { addDays, dayLabel, hm, iso, longDay, parseDay } from '../util/time'

/* §5.2: superficie pubblica, read-only, senza account. È volutamente più
   semplice della owner application: niente coda trascinabile, niente proposal,
   nessuna azione. Solo cosa è pianificato e quando arriva.

   Non esistono altre chiamate: il backend decide cosa è condivisibile (§27) e
   questa vista non prova ad aggirarlo chiedendo altro. */
const route = useRoute()
const { grid } = useBreakpoint()

const tasks = ref<ManagerTask[]>([])
const loading = ref(true)
const gone = ref(false)      // link revocato o scaduto: 404 (§5.2)
const failed = ref(false)

const STATUS_LABEL: Record<ManagerTask['status'], string> = {
  PLANNED: 'Pianificato',
  IN_PROGRESS: 'In corso',
  DELIVERED: 'Consegnato',
  BLOCKED: 'Bloccato',
  CANCELLED: 'Annullato',
  ARCHIVED: 'Archiviato',
}

onMounted(async () => {
  try {
    tasks.value = await api.get<ManagerTask[]>(`/share/${route.params.token}/planning`)
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 401)) gone.value = true
    else failed.value = true
  } finally {
    loading.value = false
  }
})

/** Solo i task con un'allocazione hanno una posizione sulla timeline. */
const placed = computed(() => tasks.value.filter((t) => t.allocation_start && t.allocation_end))

const range = computed(() => {
  const days = placed.value.flatMap((t) => [t.allocation_start!, t.allocation_end!]).sort()
  if (!days.length) return null
  const start = parseDay(days[0])
  const end = parseDay(days[days.length - 1])
  const span = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1
  return { start, end, span }
})

/** Tacche settimanali dell'asse: il lunedì è l'unità con cui si ragiona. */
const ticks = computed(() => {
  const r = range.value
  if (!r) return []
  const out: { key: string; label: string; offset: number }[] = []
  let day = addDays(r.start, -((r.start.getDay() + 6) % 7))
  while (day <= r.end) {
    if (day >= r.start) {
      const offset = Math.round((day.getTime() - r.start.getTime()) / 86_400_000)
      out.push({ key: iso(day), label: dayLabel(iso(day)), offset: (offset / r.span) * 100 })
    }
    day = addDays(day, 7)
  }
  return out
})

/** Geometria della barra di un task sull'asse comune, in percentuale. */
function bar(task: ManagerTask): { left: string; width: string } {
  const r = range.value
  if (!r) return { left: '0%', width: '0%' }
  const from = Math.round((parseDay(task.allocation_start!).getTime() - r.start.getTime()) / 86_400_000)
  const to = Math.round((parseDay(task.allocation_end!).getTime() - r.start.getTime()) / 86_400_000)
  return { left: `${(from / r.span) * 100}%`, width: `${((to - from + 1) / r.span) * 100}%` }
}

/** Su mobile la timeline non è leggibile: si legge come lista per progetto. */
const byProject = computed(() => {
  const groups = new Map<string, { name: string; color: string; tasks: ManagerTask[] }>()
  for (const task of tasks.value) {
    const name = task.project ?? 'Senza progetto'
    const group = groups.get(name) ?? { name, color: task.project_color ?? '#6b7280', tasks: [] }
    group.tasks.push(task)
    groups.set(name, group)
  }
  return [...groups.values()]
})

const totalMinutes = computed(() =>
  tasks.value.reduce((sum, task) => sum + task.planned_effort_minutes, 0),
)
</script>

<template>
  <main class="manager">
    <p v-if="loading" class="state">Caricamento…</p>

    <!-- §5.2: un link revocato o scaduto non è un errore tecnico, è un link finito. -->
    <section v-else-if="gone" class="state card notice">
      <h1>Questo link non è più valido</h1>
      <p>Il collegamento è stato revocato o è scaduto. Chiedine uno nuovo a chi te lo ha inviato.</p>
    </section>

    <section v-else-if="failed" class="state card notice">
      <h1>Piano non disponibile</h1>
      <p>Non è stato possibile caricare il piano. Riprova fra qualche minuto.</p>
    </section>

    <template v-else>
      <header class="head">
        <h1>Piano di lavoro</h1>
        <p v-if="range" class="range">
          {{ longDay(iso(range.start)) }} – {{ longDay(iso(range.end)) }}
          · {{ tasks.length }} attività · {{ hm(totalMinutes) }} pianificate
        </p>
      </header>

      <p v-if="!tasks.length" class="state">Nessuna attività pianificata al momento.</p>

      <!-- Desktop: una timeline sola, con l'asse condiviso da tutte le barre. -->
      <section v-else-if="grid" class="card timeline">
        <div class="axis">
          <span v-for="tick in ticks" :key="tick.key" :style="{ left: `${tick.offset}%` }">
            {{ tick.label }}
          </span>
        </div>
        <ul>
          <li v-for="task in tasks" :key="task.id">
            <div class="label">
              <span class="swatch" :style="{ background: task.project_color ?? '#6b7280' }"></span>
              <span>
                <strong>{{ task.title }}</strong>
                <span class="sub">{{ task.project ?? 'Senza progetto' }} · {{ hm(task.planned_effort_minutes) }}</span>
              </span>
            </div>
            <div class="track">
              <i v-for="tick in ticks" :key="tick.key" class="tick" :style="{ left: `${tick.offset}%` }"></i>
              <i
                v-if="task.allocation_start && task.allocation_end"
                class="bar"
                :style="{ ...bar(task), background: task.project_color ?? '#6b7280' }"
              ></i>
            </div>
            <div class="delivery">
              <span class="tag">{{ STATUS_LABEL[task.status] }}</span>
              <span v-if="task.delivery_date">Consegna {{ dayLabel(task.delivery_date) }}</span>
            </div>
          </li>
        </ul>
      </section>

      <!-- Mobile: lista per progetto, ordinata per data. -->
      <section v-else class="groups">
        <article v-for="group in byProject" :key="group.name" class="card group">
          <h2><span class="swatch" :style="{ background: group.color }"></span>{{ group.name }}</h2>
          <ul>
            <li v-for="task in group.tasks" :key="task.id">
              <p class="title">{{ task.title }}</p>
              <p class="meta">
                <span v-if="task.allocation_start && task.allocation_end">
                  {{ dayLabel(task.allocation_start) }} – {{ dayLabel(task.allocation_end) }} ·
                </span>
                {{ hm(task.planned_effort_minutes) }}
              </p>
              <p class="meta">
                <span class="tag">{{ STATUS_LABEL[task.status] }}</span>
                <span v-if="task.delivery_date">Consegna prevista {{ longDay(task.delivery_date) }}</span>
              </p>
            </li>
          </ul>
        </article>
      </section>
    </template>
  </main>
</template>

<style scoped>
.manager { max-width: 1000px; margin: 0 auto; padding: 16px 12px 32px; }

.head { margin-bottom: 16px; }
.head h1 { margin: 0; font-size: 22px; }
.range { margin: 4px 0 0; color: var(--text-dim); font-size: 13px; }

.state { color: var(--text-dim); padding: 12px 0; }
.notice { padding: 20px; color: var(--text); }
.notice h1 { margin: 0 0 6px; font-size: 18px; }
.notice p { margin: 0; color: var(--text-dim); }

.swatch {
  display: inline-block; width: 9px; height: 9px; border-radius: 2px;
  margin-right: 7px; flex: none;
}

/* --- timeline (desktop) --- */
.timeline { padding: 14px 16px; }
.timeline ul { list-style: none; margin: 0; padding: 0; }
.timeline li {
  display: grid;
  grid-template-columns: minmax(180px, 28%) 1fr minmax(140px, auto);
  gap: 12px; align-items: center;
  padding: 8px 0; border-top: 1px solid var(--border);
}
.label { display: flex; align-items: baseline; min-width: 0; }
.label strong { display: block; font-weight: 600; font-size: 14px; overflow-wrap: anywhere; }
.sub { display: block; color: var(--text-dim); font-size: 12px; }

.axis {
  position: relative; height: 14px; margin-left: calc(28% + 12px);
  font-size: 11px; color: var(--text-dim);
}
.axis span { position: absolute; top: 0; white-space: nowrap; text-transform: capitalize; }

.track { position: relative; height: 16px; background: var(--surface-2); border-radius: 4px; }
.tick { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border); }
.bar { position: absolute; top: 3px; height: 10px; border-radius: 3px; min-width: 4px; }

.delivery {
  display: flex; flex-direction: column; align-items: flex-end; gap: 3px;
  font-size: 12px; color: var(--text-dim); text-align: right;
}

/* --- lista per progetto (mobile) --- */
.groups { display: flex; flex-direction: column; gap: 12px; }
.group { padding: 12px 14px; }
.group h2 { display: flex; align-items: center; margin: 0 0 6px; font-size: 14px; }
.group ul { list-style: none; margin: 0; padding: 0; }
.group li { padding: 10px 0; border-top: 1px solid var(--border); }
.title { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
.meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  margin: 3px 0 0; font-size: 12px; color: var(--text-dim);
}
</style>

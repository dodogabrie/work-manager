<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type { PlanningContext, PlanningView } from '@/api/types'
import { addDays, hm, iso, parseDay, weekStart } from '@/util/time'

/* §19.2: vista compatta su più settimane. Il calendario settimanale dice come
   è fatta una giornata; questa dice dove finisce il lavoro e di quanto slitta.
   Una riga per task, una colonna per giorno, così gli slittamenti si leggono
   come spostamenti orizzontali. */

const WEEKS = 6

const loading = ref(true)
const error = ref('')
const plan = ref<PlanningView | null>(null)
const projects = ref<PlanningContext['projects']>([])
const today = ref(iso(new Date()))
const start = ref(iso(weekStart(new Date())))

const end = computed(() => iso(addDays(parseDay(start.value), WEEKS * 7 - 1)))

const days = computed(() => {
  const out: string[] = []
  for (let i = 0; i < WEEKS * 7; i++) out.push(iso(addDays(parseDay(start.value), i)))
  return out
})

/** Le settimane, per l'intestazione raggruppata. */
const weeks = computed(() =>
  Array.from({ length: WEEKS }, (_, w) => {
    const from = addDays(parseDay(start.value), w * 7)
    return { key: iso(from), label: `${from.getDate()}/${from.getMonth() + 1}` }
  }),
)

const capacityByDay = computed(() => {
  const map = new Map<string, number>()
  for (const d of plan.value?.days ?? []) map.set(d.day, d.available_minutes)
  return map
})

const projectById = computed(() => new Map(projects.value.map((p) => [p.id, p])))

/** Una riga per task pianificato: i suoi giorni occupati e la consegna. */
const rows = computed(() => {
  if (!plan.value) return []
  const minutesByTaskDay = new Map<string, number>()
  for (const s of plan.value.segments) {
    minutesByTaskDay.set(`${s.task_id}|${s.day}`, (minutesByTaskDay.get(`${s.task_id}|${s.day}`) ?? 0) + s.minutes)
  }
  return plan.value.tasks
    .filter((t) => plan.value!.segments.some((s) => s.task_id === t.id))
    .map((task) => {
      const project = task.project_id ? projectById.value.get(task.project_id) : undefined
      const cells = days.value.map((day) => ({
        day,
        minutes: minutesByTaskDay.get(`${task.id}|${day}`) ?? 0,
        closed: (capacityByDay.value.get(day) ?? 0) === 0,
      }))
      const delivery = plan.value!.delivery_dates?.[task.id] ?? null
      return {
        id: task.id,
        title: task.title,
        color: project?.color ?? 'var(--text-dim)',
        projectName: project?.name ?? null,
        effort: task.planning_effort_minutes,
        delivery,
        target: task.target_delivery_date,
        fixed: task.fixed_delivery_date,
        // §10: la target genera un warning, la fixed un conflitto.
        lateTarget: !!(task.target_delivery_date && delivery && delivery > task.target_delivery_date),
        lateFixed: !!(task.fixed_delivery_date && delivery && delivery > task.fixed_delivery_date),
        cells,
      }
    })
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [p, ctx] = await Promise.all([
      api.get<PlanningView>(`/planning?start=${start.value}&end=${end.value}`),
      api.get<PlanningContext>('/planning/context'),
    ])
    plan.value = p
    projects.value = ctx.projects
    today.value = ctx.today
  } catch {
    error.value = 'Non è stato possibile caricare la timeline.'
  } finally {
    loading.value = false
  }
}

function shift(weeks: number) {
  start.value = iso(addDays(parseDay(start.value), weeks * 7))
  load()
}

function goToday() {
  start.value = iso(weekStart(new Date()))
  load()
}

onMounted(load)
</script>

<template>
  <section class="wrap">
    <header class="bar">
      <h1>Timeline</h1>
      <div class="nav">
        <button aria-label="Settimane precedenti" @click="shift(-WEEKS)">‹</button>
        <button @click="goToday">Oggi</button>
        <button aria-label="Settimane successive" @click="shift(WEEKS)">›</button>
      </div>
    </header>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="loading" class="dim">Caricamento…</p>
    <p v-else-if="!rows.length" class="dim">Nessun lavoro pianificato in queste settimane.</p>

    <div v-else class="scroller">
      <table class="grid">
        <thead>
          <tr>
            <th class="task-col" scope="col">Task</th>
            <th v-for="w in weeks" :key="w.key" class="week" :colspan="7" scope="col">
              {{ w.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <th class="task-col" scope="row">
              <div class="task-cell">
              <span class="dot" :style="{ background: row.color }" aria-hidden="true"></span>
              <span class="meta">
                <span class="title">{{ row.title }}</span>
                <span class="sub">
                  <span v-if="row.projectName">{{ row.projectName }} · </span>{{ hm(row.effort) }}
                  <!-- Il colore non basta mai da solo: l'esito è anche scritto. -->
                  <span v-if="row.lateFixed" class="flag conflict">· oltre la data fissa</span>
                  <span v-else-if="row.lateTarget" class="flag warn">· oltre il target</span>
                </span>
              </span>
              </div>
            </th>
            <td
              v-for="cell in row.cells"
              :key="cell.day"
              class="cell"
              :class="{ closed: cell.closed, today: cell.day === today, filled: cell.minutes > 0 }"
              :style="cell.minutes ? { '--project': row.color } : undefined"
              :title="cell.minutes ? `${row.title} · ${cell.day} · ${hm(cell.minutes)}` : cell.day"
            >
              <span v-if="cell.minutes" class="visually-hidden">
                {{ row.title }} {{ cell.day }} {{ hm(cell.minutes) }}
              </span>
              <span v-if="row.delivery === cell.day" class="delivery" aria-label="consegna">◆</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.wrap { padding: 12px; display: flex; flex-direction: column; gap: 10px; min-height: 0; }
.bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h1 { margin: 0; font-size: 18px; }
.nav { display: flex; gap: 6px; }
.nav button { min-width: var(--tap); padding: 0 12px; }
.dim { color: var(--text-dim); }
.error { color: var(--danger); }

/* Il contenitore scorre per conto suo: la pagina non deve mai scorrere in
   orizzontale. */
.scroller { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); }
.grid { border-collapse: collapse; width: max-content; min-width: 100%; }

/* Il flex sta in un div interno: metterlo sul <th> toglie la cella al layout
   della tabella e disallinea intestazione e righe. */
.task-col {
  position: sticky; left: 0; z-index: 1;
  background: var(--surface);
  text-align: left; font-weight: 400;
  width: 220px; min-width: 220px; max-width: 220px;
  padding: 6px 10px;
  border-right: 1px solid var(--border);
}
.task-cell { display: flex; gap: 8px; align-items: flex-start; }
thead .task-col { font-weight: 600; font-size: 12px; }
.dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex: none; }
.meta { min-width: 0; display: flex; flex-direction: column; }
.title { font-size: 13px; overflow-wrap: anywhere; }
.sub { font-size: 11px; color: var(--text-dim); }
.flag.warn { color: var(--warning); }
.flag.conflict { color: var(--danger); }

.week {
  font-size: 11px; font-weight: 600; color: var(--text-dim);
  padding: 4px 6px; text-align: left;
  border-left: 1px solid var(--border); border-bottom: 1px solid var(--border);
}

.cell {
  width: 14px; height: 26px;
  border-bottom: 1px solid var(--surface-2);
  position: relative;
}
.cell.closed { background: var(--surface-2); }
.cell.filled { background: var(--project); }
.cell.today { box-shadow: inset 1px 0 0 var(--accent); }
.delivery { position: absolute; inset: 0; display: grid; place-items: center; font-size: 9px; color: var(--text); }

@media (min-width: 768px) {
  .cell { width: 18px; }
  .task-col { width: 260px; min-width: 260px; max-width: 260px; }
}
</style>

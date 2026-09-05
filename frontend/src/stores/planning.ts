/* Stato della schermata Planning (§32.4.1).

   Regola centrale (§3.3, §14, R9): il drag & drop NON modifica il piano.
   Riordinare significa mostrare subito l'intenzione nella coda, chiedere al
   backend una PlanningProposal (che simula senza applicare) e rendere la
   preview finché l'utente non approva o annulla.

   I componenti non parlano con l'API: chiamano solo le azioni di qui. */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, api } from '../api/client'
import type {
  CapacityException,
  CapacityView,
  DayCapacity,
  PlanningContext,
  PlanningSegment,
  PlanningView,
  Project,
  Proposal,
  Task,
  TaskOrProposal,
} from '../api/types'
import { addDays, iso, longDay, weekStart } from '../util/time'

/** Un blocco di lavoro su un giorno, pronto per il calendario. */
export interface DayBlock {
  taskId: string
  title: string
  minutes: number
  color: string
  project: string | null
  /** true = esiste solo nella preview della proposal pendente. */
  preview: boolean
  /** true = la proposal lo sposta rispetto al piano confermato. */
  moved: boolean
}

export interface DayModel {
  day: string
  isToday: boolean
  baseMinutes: number
  meetingMinutes: number
  availableMinutes: number
  plannedMinutes: number
  remainingMinutes: number
  exception: CapacityException | null
  blocks: DayBlock[]
}

const NEUTRAL = '#8a8a84'

export const usePlanningStore = defineStore('planning', () => {
  const today = ref(iso(new Date()))
  const anchor = ref(weekStart(new Date()))          // lunedì visualizzato
  const planVersion = ref(0)

  const queue = ref<Task[]>([])                      // ordine mostrato (può essere l'intenzione)
  const serverQueue = ref<Task[]>([])                // ordine confermato dal backend
  const segments = ref<PlanningSegment[]>([])
  /** task_id -> ultimo giorno occupato, su tutto il piano (non solo la finestra). */
  const planDeliveries = ref<Record<string, string>>({})
  const days = ref<DayCapacity[]>([])
  const weekly = ref<Record<string, number>>({})
  const exceptions = ref<CapacityException[]>([])
  const projects = ref<Project[]>([])
  const inbox = ref<Task[]>([])

  const proposal = ref<Proposal | null>(null)
  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')
  /** §26: il piano è cambiato sotto la proposal, serve un ricalcolo. */
  const stale = ref(false)

  const weekDays = computed(() =>
    Array.from({ length: 7 }, (_, i) => iso(addDays(anchor.value, i))),
  )
  const rangeStart = computed(() => weekDays.value[0])
  const rangeEnd = computed(() => weekDays.value[6])

  const projectById = computed(() => new Map(projects.value.map((p) => [p.id, p])))
  // Anche i task ancora in Inbox: una proposal pendente può già mostrarli nel
  // calendario in preview, e servono titolo e progetto per renderli.
  const taskById = computed(
    () => new Map([...serverQueue.value, ...inbox.value, ...queue.value].map((t) => [t.id, t])),
  )

  // ------------------------------------------------------------ preview

  const movedTaskIds = computed(
    () => new Set((proposal.value?.simulation.changes ?? []).map((c) => c.task_id)),
  )
  const hasProposal = computed(() => proposal.value !== null)
  const warnings = computed(() => proposal.value?.simulation.warnings ?? [])
  const conflicts = computed(() => proposal.value?.simulation.conflicts ?? [])
  /** §14.1: un conflitto hard non è confermabile; i warning sì (§14.2). */
  const blocked = computed(() => conflicts.value.length > 0)

  /** Data di consegna per task = ultimo giorno con lavoro allocato. */
  function deliveries(source: { task_id: string; day: string }[]): Map<string, string> {
    const out = new Map<string, string>()
    for (const s of source) {
      const known = out.get(s.task_id)
      if (!known || s.day > known) out.set(s.task_id, s.day)
    }
    return out
  }

  /** Le consegne del piano intero, non della sola settimana caricata: la
   *  prossima consegna cade quasi sempre fuori dalla finestra che si guarda. */
  const confirmedDeliveries = computed(() => {
    const fromPlan = new Map(Object.entries(planDeliveries.value))
    return fromPlan.size ? fromPlan : deliveries(segments.value)
  })

  const nextDelivery = computed(() => {
    let best: { title: string; day: string } | null = null
    for (const [taskId, day] of confirmedDeliveries.value) {
      if (day < today.value) continue
      const task = taskById.value.get(taskId)
      if (!task) continue
      if (!best || day < best.day) best = { title: task.title, day }
    }
    return best
  })

  const todayCapacity = computed(
    () => days.value.find((d) => d.day === today.value)
      ?? { day: today.value, available_minutes: 0, planned_minutes: 0 },
  )

  /** Il calendario della settimana: capacità, meeting, assenze, blocchi, residuo (§19). */
  const calendar = computed<DayModel[]>(() => {
    const exceptionByDay = new Map(exceptions.value.map((e) => [e.day, e]))
    const capacityByDay = new Map(days.value.map((d) => [d.day, d]))
    const preview = proposal.value?.simulation.segments ?? null

    return weekDays.value.map((day) => {
      const cap = capacityByDay.get(day)
      const exception = exceptionByDay.get(day) ?? null
      const weekday = (new Date(day + 'T00:00:00').getDay() + 6) % 7
      const base = exception ? exception.minutes : (weekly.value[String(weekday)] ?? 0)
      const available = cap?.available_minutes ?? 0

      const rows = preview
        ? preview.filter((s) => s.date === day).map((s) => ({ task_id: s.task_id, minutes: s.minutes }))
        : segments.value.filter((s) => s.day === day).map((s) => ({ task_id: s.task_id, minutes: s.minutes }))

      const confirmedHere = new Set(
        segments.value.filter((s) => s.day === day).map((s) => s.task_id),
      )
      const blocks: DayBlock[] = rows.map((row) => {
        const task = taskById.value.get(row.task_id)
        const project = task?.project_id ? projectById.value.get(task.project_id) : undefined
        return {
          taskId: row.task_id,
          title: task?.title ?? 'Task',
          minutes: row.minutes,
          color: project?.color ?? NEUTRAL,
          project: project?.name ?? null,
          preview: preview !== null && !confirmedHere.has(row.task_id),
          moved: preview !== null && movedTaskIds.value.has(row.task_id),
        }
      })

      const planned = rows.reduce((sum, r) => sum + r.minutes, 0)
      return {
        day,
        isToday: day === today.value,
        baseMinutes: base,
        meetingMinutes: Math.max(0, base - available),
        availableMinutes: available,
        plannedMinutes: planned,
        remainingMinutes: available - planned,
        exception,
        blocks,
      }
    })
  })

  /** Riassunto testuale dell'impatto per la barra proposal (§32.4.2). */
  const impact = computed(() => {
    const changes = proposal.value?.simulation.changes ?? []
    // Spostare un task dove già si trova è una richiesta legittima che non
    // cambia il piano: dirlo è più utile che annunciare "0 task spostati".
    if (!changes.length) return 'Nessun cambiamento al piano'
    const moved = changes.filter((c) => c.old_delivery !== c.new_delivery || c.shift_days !== 0)
    const parts: string[] = [`${changes.length} task spostat${changes.length === 1 ? 'o' : 'i'}`]
    const slip = moved.find((c) => c.shift_days !== 0 && c.new_delivery)
    if (slip?.new_delivery) {
      const task = taskById.value.get(slip.task_id)
      parts.push(`${task?.title ?? 'Un task'} → ${longDay(slip.new_delivery)}`)
    }
    return parts.join(' · ')
  })

  // ------------------------------------------------------------ azioni

  function fail(e: unknown): never {
    error.value = e instanceof ApiError ? e.message : 'Errore imprevisto'
    throw e
  }

  async function loadWindow() {
    const [plan, capacity] = await Promise.all([
      api.get<PlanningView>(`/planning?start=${rangeStart.value}&end=${rangeEnd.value}`),
      api.get<CapacityView>(`/capacity?start=${rangeStart.value}&end=${rangeEnd.value}`),
    ])
    planVersion.value = plan.plan_version
    serverQueue.value = plan.tasks
    if (!proposal.value) queue.value = [...plan.tasks]
    segments.value = plan.segments
    planDeliveries.value = plan.delivery_dates ?? {}
    days.value = plan.days
    weekly.value = capacity.weekly_minutes
    exceptions.value = capacity.exceptions
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      // Il contesto porta progetti, inbox e proposal già pendenti in una sola chiamata.
      const context = await api.get<PlanningContext>('/planning/context')
      today.value = context.today
      projects.value = context.projects
      inbox.value = context.inbox
      proposal.value = context.pending_proposals[0] ?? null
      await loadWindow()
      if (proposal.value) applyIntentToQueue(proposal.value)
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Errore imprevisto'
    } finally {
      loading.value = false
    }
  }

  /** Riflette nella coda mostrata la posizione proposta da una proposal pendente. */
  function applyIntentToQueue(pending: Proposal) {
    const tasks = (pending.intent?.tasks ?? {}) as Record<string, { queue_position?: string }>
    const positions = new Map<string, number>()
    for (const [id, fields] of Object.entries(tasks)) {
      if (fields?.queue_position != null) positions.set(id, Number(fields.queue_position))
    }
    if (!positions.size) return
    queue.value = [...serverQueue.value].sort((a, b) => {
      const pa = positions.get(a.id) ?? Number(a.queue_position ?? 0)
      const pb = positions.get(b.id) ?? Number(b.queue_position ?? 0)
      return pa - pb
    })
  }

  async function setWeek(delta: number) {
    anchor.value = addDays(anchor.value, delta * 7)
    await loadWindow()
  }

  async function goToday() {
    anchor.value = weekStart(new Date())
    await loadWindow()
  }

  /**
   * §14 / R9: la nuova posizione è solo un'intenzione. La coda mostra subito
   * l'ordine nuovo (ottimistico), il backend risponde con una proposal e il
   * calendario passa in preview.
   *
   * Una sola intenzione per volta: un secondo riordino sostituisce il primo,
   * così l'ordine mostrato corrisponde sempre a ciò che `Applica` applicherà.
   */
  async function reorder(taskId: string, ordered: Task[]) {
    const previous = queue.value
    queue.value = ordered
    const index = ordered.findIndex((t) => t.id === taskId)
    const before_id = index > 0 ? ordered[index - 1].id : null
    const after_id = index < ordered.length - 1 ? ordered[index + 1].id : null
    busy.value = true
    error.value = ''
    stale.value = false
    try {
      if (proposal.value) await api.post(`/proposals/${proposal.value.id}/reject`)
      proposal.value = await api.post<Proposal>(`/tasks/${taskId}/move`, { before_id, after_id })
    } catch (e) {
      queue.value = previous
      error.value = e instanceof ApiError ? e.message : 'Simulazione fallita'
    } finally {
      busy.value = false
    }
  }

  /** Sposta senza drag: serve da tastiera e sulle liste lunghe (menu ⋮). */
  function moveTo(taskId: string, target: number) {
    const ordered = [...queue.value]
    const from = ordered.findIndex((t) => t.id === taskId)
    if (from < 0) return Promise.resolve()
    const to = Math.max(0, Math.min(ordered.length - 1, target))
    if (from === to) return Promise.resolve()
    const [task] = ordered.splice(from, 1)
    ordered.splice(to, 0, task)
    return reorder(taskId, ordered)
  }

  async function apply() {
    if (!proposal.value || blocked.value) return
    busy.value = true
    error.value = ''
    try {
      await api.post(`/proposals/${proposal.value.id}/approve`)
      proposal.value = null
      stale.value = false
      await load()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) stale.value = true
      else error.value = e instanceof ApiError ? e.message : 'Applicazione fallita'
    } finally {
      busy.value = false
    }
  }

  async function discard() {
    const pending = proposal.value
    proposal.value = null
    stale.value = false
    queue.value = [...serverQueue.value]
    if (!pending) return
    busy.value = true
    try {
      await api.post(`/proposals/${pending.id}/reject`)
    } catch {
      // La proposal era già risolta lato server: l'ordine mostrato è comunque
      // tornato quello confermato, non c'è nulla da dire all'utente.
    } finally {
      busy.value = false
      await loadWindow()
    }
  }

  /** §12.1/§26: una proposal stale va ricalcolata prima di poter essere approvata. */
  async function recalculate() {
    if (!proposal.value) return
    busy.value = true
    error.value = ''
    try {
      proposal.value = await api.post<Proposal>(`/proposals/${proposal.value.id}/recalculate`)
      stale.value = false
      await loadWindow()
      applyIntentToQueue(proposal.value)
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Ricalcolo fallito'
    } finally {
      busy.value = false
    }
  }

  /** §6.2: per aggiungere basta il titolo. Il task nasce in Inbox, fuori dal piano. */
  async function quickAdd(title: string, description?: string) {
    const task = await api.post<Task>('/inbox/quick-add', { title, description }).catch(fail)
    inbox.value = [...inbox.value, task]
    return task
  }

  /** §32.4.3: `Pianifica` mette il task in fondo alla coda — via proposal (R3). */
  /** §23.2: è un soft delete — il task sparisce dalla vista, la storia resta. */
  async function discardFromInbox(taskId: string) {
    error.value = ''
    busy.value = true
    try {
      await api.del(`/tasks/${taskId}`)
      inbox.value = inbox.value.filter((t) => t.id !== taskId)
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Eliminazione fallita'
    } finally {
      busy.value = false
    }
  }

  async function planFromInbox(taskId: string) {
    busy.value = true
    error.value = ''
    try {
      if (proposal.value) await api.post(`/proposals/${proposal.value.id}/reject`)
      const result = await api.post<TaskOrProposal>(`/tasks/${taskId}/status`, { status: 'PLANNED' })
      proposal.value = result.proposal
      await loadWindow()
      // Il task entra davvero in coda solo se la proposal viene approvata:
      // fino ad allora esiste solo nella preview del calendario.
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Pianificazione fallita'
      throw e
    } finally {
      busy.value = false
    }
  }

  return {
    today, anchor, planVersion, queue, serverQueue, segments, days, projects, inbox,
    proposal, loading, busy, error, stale,
    weekDays, rangeStart, rangeEnd, projectById, taskById,
    calendar, impact, warnings, conflicts, blocked, hasProposal, movedTaskIds,
    nextDelivery, todayCapacity, confirmedDeliveries,
    load, setWeek, goToday, reorder, moveTo, apply, discard, recalculate,
    quickAdd, planFromInbox, discardFromInbox,
  }
})

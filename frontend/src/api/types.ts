/* Rispecchia i DTO del backend (app/schemas/__init__.py).
   Gli effort sono SEMPRE in minuti (§11.1): la conversione in ore avviene solo
   nella resa, in util/time.ts. */

export type TaskStatus =
  | 'INBOX' | 'PLANNED' | 'IN_PROGRESS' | 'READY' | 'DELIVERED'
  | 'BLOCKED' | 'CANCELLED' | 'ARCHIVED'

export interface Task {
  id: string
  title: string
  description: string | null
  project_id: string | null
  status: TaskStatus
  planning_effort_minutes: number
  proposed_effort_minutes: number | null
  estimate_confidence: string | null
  target_delivery_date: string | null
  fixed_delivery_date: string | null
  queue_position: string | number | null
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  name: string
  color: string
  archived: boolean
}

/** GET /api/planning -> segmenti confermati. */
export interface PlanningSegment {
  task_id: string
  day: string
  minutes: number
  locked: boolean
}

/** simulation.segments usa `date`, non `day` (services/planning.segment_json). */
export interface SimulatedSegment {
  task_id: string
  date: string
  minutes: number
  locked: boolean
}

export interface DayCapacity {
  day: string
  available_minutes: number
  planned_minutes: number
}

export interface CapacityException {
  id: string
  day: string
  minutes: number
  kind: 'VACATION' | 'LEAVE' | 'REDUCED' | 'EXTRA'
  note: string | null
}

export interface CapacityView {
  weekly_minutes: Record<string, number>
  exceptions: CapacityException[]
  days: DayCapacity[]
}

export interface PlanningReason {
  type: string
  task_id: string | null
  date: string | null
  minutes: number | null
  severity: 'info' | 'warning' | 'conflict'
  message: string
}

export interface PlanChange {
  task_id: string
  old_start: string | null
  new_start: string | null
  old_delivery: string | null
  new_delivery: string | null
  shift_days: number
}

/** §12. Nessuna modifica al piano confermato avviene senza passare di qui. */
export interface Proposal {
  id: string
  kind: string
  origin: string
  status: string
  base_plan_version: number
  intent: Record<string, unknown>
  simulation: {
    segments: SimulatedSegment[]
    delivery_dates: Record<string, string>
    changes: PlanChange[]
    warnings: PlanningReason[]
    conflicts: PlanningReason[]
    reasons: PlanningReason[]
  }
  created_at: string
  resolved_at: string | null
}

export interface PlanningView {
  plan_version: number
  tasks: Task[]
  segments: PlanningSegment[]
  days: DayCapacity[]
  /** task_id -> ultimo giorno occupato, calcolato sull'intero piano. */
  delivery_dates: Record<string, string>
}

export interface PlanningContext {
  today: string
  plan_version: number
  projects: Project[]
  inbox: Task[]
  queue: Task[]
  segments: PlanningSegment[]
  capacity: DayCapacity[]
  pending_proposals: Proposal[]
  constraints: string[]
}

export interface TaskOrProposal {
  task: Task | null
  proposal: Proposal | null
}

// ---------------------------------------------------------------- history (§22, §23)

/** §23.1. `entities` è un JSON libero: la history non ne conosce la forma. */
export interface Action {
  id: string
  action_type: string
  origin: string
  actor: string | null
  created_at: string
  entities: Record<string, unknown>
  reversible: boolean
  undone: boolean
  inverse_of_id: string | null
  snapshot_id: string | null
}

export interface Snapshot {
  id: string
  plan_version: number
  created_at: string
  note: string | null
}

/** §23.4: i quattro esiti possibili di un undo/redo, come valori non eccezioni. */
export interface UndoResult {
  status: 'applied' | 'proposal' | 'conflict' | 'impossible'
  message: string
  action: Action | null
  proposal: Proposal | null
}

// ---------------------------------------------------------------- impostazioni

export interface ExceptionOrProposal {
  exception: CapacityException | null
  proposal: Proposal | null
}

export interface CalendarConnection {
  id: string
  name: string
  ics_url: string
  enabled: boolean
  last_synced_at: string | null
  last_sync_error: string | null
  created_at: string
}

export interface SyncResult {
  connection: CalendarConnection
  events_upserted: number
  events_cancelled: number
  proposal: Proposal | null
}

export interface ApiToken {
  id: string
  label: string
  scopes: string[]
  revoked_at: string | null
  last_used_at: string | null
  created_at: string
}

/** §28: `token` esiste solo nella risposta di creazione, mai più. */
export interface ApiTokenCreated extends ApiToken {
  token: string
}

export interface ShareLink {
  id: string
  label: string
  kind: string
  expires_at: string | null
  revoked_at: string | null
  last_accessed_at: string | null
  created_at: string
}

export interface ShareLinkCreated extends ShareLink {
  token: string
  url: string
}

/** GET /api/share/{token}/planning -> TaskManagerView (§5.2, §27).
    Deliberatamente povero: è tutto ciò che un manager può vedere. */
export interface ManagerTask {
  id: string
  title: string
  project: string | null
  project_color: string | null
  planned_effort_minutes: number
  allocation_start: string | null
  allocation_end: string | null
  delivery_date: string | null
  status: 'PLANNED' | 'IN_PROGRESS' | 'DELIVERED' | 'BLOCKED' | 'CANCELLED' | 'ARCHIVED'
}

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

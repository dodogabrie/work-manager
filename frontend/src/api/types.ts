/* Rispecchia i DTO del backend. Gli effort sono SEMPRE in minuti (§11.1):
   la conversione in ore avviene solo nella resa. */

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
  queue_position: string | null
}

export interface PlanningSegment {
  task_id: string
  day: string
  minutes: number
  locked: boolean
}

export interface DayCapacity {
  day: string
  base_minutes: number
  meeting_minutes: number
  available_minutes: number
  planned_minutes: number
  exception: { kind: string; note: string | null } | null
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
  title: string
  old_delivery: string | null
  new_delivery: string | null
  shift_days: number
}

/** §12. Nessuna modifica al piano confermato avviene senza passare di qui. */
export interface Proposal {
  id: string
  kind: string
  origin: string
  status: 'pending' | 'approved' | 'rejected' | 'stale' | 'applied'
  base_plan_version: number
  simulation: {
    segments: PlanningSegment[]
    changes: PlanChange[]
    warnings: PlanningReason[]
    conflicts: PlanningReason[]
    reasons: PlanningReason[]
  }
}

export interface PlanningView {
  plan_version: number
  segments: PlanningSegment[]
  capacity: DayCapacity[]
  queue: Task[]
  delivery_dates: Record<string, string>
}

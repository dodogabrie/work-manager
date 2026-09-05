/* Un solo check sul punto che può rompersi in silenzio: il merge fra piano
   confermato e preview della proposal, e il fatto che il riordino non tocchi
   il piano finché non è approvato (§14). */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'

import { usePlanningStore } from './planning'

const TODAY = '2026-09-07'   // lunedì
const A = 'aaaa'
const B = 'bbbb'

const PROPOSAL = {
  id: 'p1', kind: 'QUEUE_REORDER', origin: 'UI', status: 'pending',
  base_plan_version: 1, intent: { tasks: { [B]: { queue_position: '500' } } },
  simulation: {
    segments: [
      { task_id: B, date: TODAY, minutes: 120, locked: false },
      { task_id: A, date: TODAY, minutes: 360, locked: false },
    ],
    delivery_dates: {}, changes: [{ task_id: A, old_start: TODAY, new_start: TODAY,
      old_delivery: TODAY, new_delivery: '2026-09-08', shift_days: 1 }],
    warnings: [], conflicts: [], reasons: [],
  },
  created_at: '', resolved_at: null,
}

function task(id: string, title: string, position: string) {
  return {
    id, title, description: null, project_id: null, status: 'PLANNED',
    planning_effort_minutes: 480, proposed_effort_minutes: null,
    estimate_confidence: null, target_delivery_date: null, fixed_delivery_date: null,
    queue_position: position, created_at: '', updated_at: '',
  }
}

const ROUTES: Record<string, unknown> = {
  '/planning/context': {
    today: TODAY, plan_version: 1, projects: [], inbox: [], queue: [],
    segments: [], capacity: [], pending_proposals: [], constraints: [],
  },
  '/planning?': {
    plan_version: 1,
    tasks: [task(A, 'Export', '1000'), task(B, 'Fix', '2000')],
    segments: [{ task_id: A, day: TODAY, minutes: 480, locked: false }],
    days: [{ day: TODAY, available_minutes: 480, planned_minutes: 480 }],
  },
  '/capacity?': { weekly_minutes: { '0': 480, '5': 0, '6': 0 }, exceptions: [], days: [] },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const path = url.replace(/^.*\/api/, '')
    const key = Object.keys(ROUTES).find((k) => path.startsWith(k))
    const body = key ? ROUTES[key] : PROPOSAL
    return { ok: true, status: 200, json: async () => body } as Response
  }))
})

test('il piano confermato resta tale finché la proposal non è applicata', async () => {
  const store = usePlanningStore()
  store.anchor = new Date(2026, 8, 7)
  await store.load()

  const monday = store.calendar.find((d) => d.day === TODAY)!
  expect(monday.blocks.map((b) => b.taskId)).toEqual([A])
  expect(monday.remainingMinutes).toBe(0)

  await store.reorder(B, [store.queue[1], store.queue[0]])

  // I segmenti confermati non sono cambiati: solo la preview lo è (§3.3).
  expect(store.segments).toHaveLength(1)
  const preview = store.calendar.find((d) => d.day === TODAY)!
  expect(preview.blocks.map((b) => b.taskId)).toEqual([B, A])
  expect(preview.blocks.find((b) => b.taskId === B)!.preview).toBe(true)
  expect(preview.blocks.find((b) => b.taskId === A)!.moved).toBe(true)
  expect(store.blocked).toBe(false)
  expect(store.impact).toContain('1 task spostato')
})

/* Un solo check sul punto che può rompersi in silenzio: §11.3 — un'assenza su
   un giorno già pianificato NON si applica, diventa una proposal da confermare.
   Ignorare il campo `proposal` della risposta sarebbe un bug invisibile: la UI
   direbbe "salvato" mentre il piano non è cambiato. */

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, test, vi } from 'vitest'

import { useProposalStore } from './proposals'
import { useSettingsStore } from './settings'

const PROPOSAL = {
  id: 'p1', kind: 'CAPACITY_CHANGE', origin: 'UI', status: 'pending',
  base_plan_version: 3, intent: { capacity: { '2026-09-10': 0 } },
  simulation: {
    segments: [], delivery_dates: {},
    changes: [{ task_id: 'aaaa', old_start: null, new_start: null,
      old_delivery: '2026-09-10', new_delivery: '2026-09-11', shift_days: 1 }],
    warnings: [], conflicts: [], reasons: [],
  },
  created_at: '', resolved_at: null,
}

const EXCEPTION = { id: 'e1', day: '2026-09-10', minutes: 0, kind: 'VACATION', note: null }

/** Risposta variabile: il test cambia `answer` fra i due esiti di §11.3. */
let answer: unknown

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const path = url.replace(/^.*\/api/, '')
    if (path.startsWith('/capacity?')) {
      return { ok: true, status: 200, json: async () => ({
        weekly_minutes: { '0': 480 }, exceptions: [EXCEPTION], days: [],
      }) } as Response
    }
    if (path === '/tasks') {
      return { ok: true, status: 200, json: async () => [] } as Response
    }
    return { ok: true, status: 200, json: async () => answer } as Response
  }))
})

test('senza piano da spostare l\'assenza si applica subito', async () => {
  answer = { exception: EXCEPTION, proposal: null }
  const store = useSettingsStore()

  const applied = await store.saveException({
    id: null, day: '2026-09-10', minutes: 0, kind: 'VACATION', note: '',
  })

  expect(applied).toBe(true)
  expect(useProposalStore().pending).toBe(false)
  expect(store.exceptions).toHaveLength(1)
})

test('su un piano esistente l\'assenza diventa una proposal da confermare', async () => {
  answer = { exception: null, proposal: PROPOSAL }
  const store = useSettingsStore()

  const applied = await store.saveException({
    id: null, day: '2026-09-10', minutes: 0, kind: 'VACATION', note: '',
  })

  expect(applied).toBe(false)
  const proposals = useProposalStore()
  expect(proposals.pending).toBe(true)
  expect(proposals.blocked).toBe(false)
  expect(proposals.impact).toContain('1 task spostato')
})

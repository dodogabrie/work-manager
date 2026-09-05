/* La proposal pendente fuori dalla schermata Planning (§12, §19.1).

   Impostazioni e History producono proposal esattamente come il drag & drop:
   un'eccezione di capacità su un piano esistente (§11.3) e un undo che tocca il
   piano (§23.3) non applicano nulla, propongono. Il ciclo
   approve/reject/recalculate è lo stesso, quindi vive qui una volta sola invece
   che in due view.

   `stores/planning.ts` NON usa questo store: la sua proposal è intrecciata con
   la coda mostrata in anteprima e con il calendario, e separarla non
   semplificherebbe niente. */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, api } from '../api/client'
import type { Proposal, Task } from '../api/types'
import { longDay } from '../util/time'

export const useProposalStore = defineStore('proposal', () => {
  const proposal = ref<Proposal | null>(null)
  /** task_id -> titolo, per non mostrare uuid nell'impatto. */
  const titles = ref<Record<string, string>>({})
  const busy = ref(false)
  const error = ref('')
  /** §26: il piano è cambiato sotto la proposal, serve un ricalcolo. */
  const stale = ref(false)

  const changes = computed(() => proposal.value?.simulation.changes ?? [])
  const warnings = computed(() => proposal.value?.simulation.warnings ?? [])
  const conflicts = computed(() => proposal.value?.simulation.conflicts ?? [])
  /** §14.1: un conflitto hard non è approvabile; i warning sì (§14.2). */
  const blocked = computed(() => conflicts.value.length > 0)
  const pending = computed(() => proposal.value !== null)

  function titleOf(taskId: string): string {
    return titles.value[taskId] ?? taskId.slice(0, 8)
  }

  const impact = computed(() => {
    if (!changes.value.length) return 'Nessun cambiamento al piano'
    const parts = [`${changes.value.length} task spostat${changes.value.length === 1 ? 'o' : 'i'}`]
    const slip = changes.value.find((c) => c.shift_days !== 0 && c.new_delivery)
    if (slip?.new_delivery) parts.push(`${titleOf(slip.task_id)} → ${longDay(slip.new_delivery)}`)
    return parts.join(' · ')
  })

  /** Mostra una proposal appena ricevuta da una qualsiasi API. */
  async function present(next: Proposal | null) {
    proposal.value = next
    stale.value = false
    error.value = ''
    if (next && !Object.keys(titles.value).length) {
      const tasks = await api.get<Task[]>('/tasks').catch(() => [] as Task[])
      titles.value = Object.fromEntries(tasks.map((t) => [t.id, t.title]))
    }
  }

  /** true se il piano è stato davvero modificato: chi chiama ricarica i suoi dati. */
  async function approve(): Promise<boolean> {
    if (!proposal.value || blocked.value) return false
    busy.value = true
    error.value = ''
    try {
      await api.post(`/proposals/${proposal.value.id}/approve`)
      proposal.value = null
      stale.value = false
      return true
    } catch (e) {
      // §26: 409 = qualcun altro ha cambiato il piano nel frattempo. Non è un
      // errore da leggere e chiudere: si ricalcola e si riprova.
      if (e instanceof ApiError && e.status === 409) stale.value = true
      else error.value = e instanceof ApiError ? e.message : 'Applicazione fallita'
      return false
    } finally {
      busy.value = false
    }
  }

  async function reject() {
    const current = proposal.value
    proposal.value = null
    stale.value = false
    error.value = ''
    if (!current) return
    // Se era già risolta lato server non c'è niente da dire: la UI è comunque
    // tornata a mostrare il piano confermato.
    await api.post(`/proposals/${current.id}/reject`).catch(() => undefined)
  }

  async function recalculate() {
    if (!proposal.value) return
    busy.value = true
    error.value = ''
    try {
      proposal.value = await api.post<Proposal>(`/proposals/${proposal.value.id}/recalculate`)
      stale.value = false
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Ricalcolo fallito'
    } finally {
      busy.value = false
    }
  }

  return {
    proposal, titles, busy, error, stale,
    changes, warnings, conflicts, blocked, pending, impact,
    titleOf, present, approve, reject, recalculate,
  }
})

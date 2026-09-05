/* History, undo e redo non lineari (§22, §23).

   Il punto delicato è §23.4: l'undo non è "torna indietro di uno". Si può
   tentare su qualsiasi azione reversibile, e viene validato contro lo stato
   corrente — quindi ha quattro esiti diversi, non uno solo:

     applied     applicato subito, l'azione non toccava il piano
     proposal    tocca il piano: c'è una preview da confermare (§23.3)
     conflict    la contro-operazione violerebbe un vincolo hard
     impossible  non reversibile, già annullata, o niente da ripristinare

   Lo store li conserva per azione, così la riga che l'utente ha toccato può
   spiegare cosa è successo lì e non altrove. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '../api/client'
import type { Action, Snapshot, UndoResult } from '../api/types'
import { useProposalStore } from './proposals'

/** L'esito mostrato accanto a una riga della history. */
export interface Outcome {
  status: UndoResult['status']
  message: string
  /** 'undo' | 'redo': quale tentativo ha prodotto l'esito. */
  verb: 'undo' | 'redo'
}

/** §23.1: le origini possibili di un'azione, in italiano. */
const ORIGINS: Record<string, string> = {
  UI: 'Interfaccia',
  API: 'Claude / API',
  CALENDAR: 'Calendario',
  SYSTEM: 'Sistema',
}

export function originLabel(origin: string): string {
  return ORIGINS[origin.toUpperCase()] ?? origin
}

/** Le entità coinvolte sono un JSON libero: se ne mostra una sintesi onesta. */
export function entityLabels(entities: Record<string, unknown>): string[] {
  return Object.entries(entities).map(([key, value]) => {
    const count = Array.isArray(value) ? value.length : 1
    return Array.isArray(value) ? `${key}: ${count}` : `${key}: ${String(value).slice(0, 8)}`
  })
}

export const useHistoryStore = defineStore('history', () => {
  const proposals = useProposalStore()

  const actions = ref<Action[]>([])
  const snapshots = ref<Snapshot[]>([])
  const outcomes = ref<Record<string, Outcome>>({})

  const loading = ref(false)
  const busy = ref<string | null>(null)   // id dell'azione in corso
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const [log, snaps] = await Promise.all([
        api.get<Action[]>('/actions?limit=100'),
        api.get<Snapshot[]>('/snapshots?limit=50'),
      ])
      actions.value = log
      snapshots.value = snaps
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : 'Caricamento della history fallito'
    } finally {
      loading.value = false
    }
  }

  /** §23.6: report e eventi arrivati dal calendario non sono annullabili. */
  function undoBlockedReason(action: Action): string | null {
    if (!action.reversible) {
      return 'Azione non reversibile: registra un fatto esterno o un output, non una decisione di piano (§23.6).'
    }
    if (action.undone) return 'Già annullata. Usa Redo per riapplicarla.'
    return null
  }

  function redoBlockedReason(action: Action): string | null {
    if (!action.reversible) return 'Azione non reversibile.'
    if (!action.undone) return 'Non ancora annullata: non c\'è niente da riapplicare.'
    return null
  }

  async function run(verb: 'undo' | 'redo', action: Action) {
    busy.value = action.id
    error.value = ''
    try {
      const result = await api.post<UndoResult>(`/actions/${action.id}/${verb}`)
      outcomes.value = {
        ...outcomes.value,
        [action.id]: { status: result.status, message: result.message, verb },
      }
      // §23.3: se tocca il piano non è applicato, è proposto. La preview va
      // mostrata anche quando l'esito è `conflict`: serve a capire perché.
      if (result.proposal) await proposals.present(result.proposal)
      if (result.status === 'applied') await load()
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : `${verb} fallito`
    } finally {
      busy.value = null
    }
  }

  const undo = (action: Action) => run('undo', action)
  const redo = (action: Action) => run('redo', action)

  function clearOutcome(actionId: string) {
    const { [actionId]: _dropped, ...rest } = outcomes.value
    outcomes.value = rest
  }

  return {
    actions, snapshots, outcomes, loading, busy, error,
    load, undo, redo, undoBlockedReason, redoBlockedReason, clearOutcome,
  }
})

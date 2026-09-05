/* Impostazioni: capacità (§11.2), assenze (§11.3), integrazioni calendario
   (§32.18), token API e link manager (§5.2, §5.3, §28).

   Regola che tiene insieme la schermata: modificare la capacità di un giorno su
   cui c'è già del piano NON applica niente, propone (§11.3). L'API risponde con
   `{exception|proposal}` e la proposal va portata all'utente, non ignorata. */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, api } from '../api/client'
import type {
  ApiToken,
  ApiTokenCreated,
  CalendarConnection,
  CapacityException,
  CapacityView,
  ExceptionOrProposal,
  ShareLink,
  ShareLinkCreated,
  SyncResult,
} from '../api/types'
import { addDays, iso } from '../util/time'
import { useProposalStore } from './proposals'

/** Le eccezioni sono richieste su una finestra: abbastanza larga da mostrare le
 *  ferie già inserite, abbastanza stretta da non scaricare anni di giorni. */
const PAST_DAYS = 30
const FUTURE_DAYS = 300

export const WEEKDAYS = [
  { key: '0', label: 'Lunedì', short: 'lun' },
  { key: '1', label: 'Martedì', short: 'mar' },
  { key: '2', label: 'Mercoledì', short: 'mer' },
  { key: '3', label: 'Giovedì', short: 'gio' },
  { key: '4', label: 'Venerdì', short: 'ven' },
  { key: '5', label: 'Sabato', short: 'sab' },
  { key: '6', label: 'Domenica', short: 'dom' },
]

export const EXCEPTION_KINDS = [
  { value: 'VACATION', label: 'Ferie' },
  { value: 'LEAVE', label: 'Permesso' },
  { value: 'REDUCED', label: 'Giornata ridotta' },
  { value: 'EXTRA', label: 'Capacità extra' },
] as const

export interface ExceptionDraft {
  id: string | null
  day: string
  minutes: number
  kind: string
  note: string
}

export const useSettingsStore = defineStore('settings', () => {
  const proposals = useProposalStore()

  const weekly = ref<Record<string, number>>({})
  const exceptions = ref<CapacityException[]>([])
  const integrations = ref<CalendarConnection[]>([])
  const tokens = ref<ApiToken[]>([])
  const links = ref<ShareLink[]>([])

  /** §28: il segreto in chiaro esiste solo qui, e solo fino al reload. */
  const newToken = ref<ApiTokenCreated | null>(null)
  const newLink = ref<ShareLinkCreated | null>(null)

  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')
  const notice = ref('')

  const weeklyTotal = computed(() =>
    WEEKDAYS.reduce((sum, d) => sum + (weekly.value[d.key] ?? 0), 0),
  )
  const activeTokens = computed(() => tokens.value.filter((t) => !t.revoked_at))
  const activeLinks = computed(() => links.value.filter((l) => !l.revoked_at))

  function fail(e: unknown, fallback: string) {
    error.value = e instanceof ApiError ? e.message : fallback
  }

  async function loadCapacity() {
    const today = new Date()
    const start = iso(addDays(today, -PAST_DAYS))
    const end = iso(addDays(today, FUTURE_DAYS))
    const view = await api.get<CapacityView>(`/capacity?start=${start}&end=${end}`)
    weekly.value = Object.fromEntries(
      Object.entries(view.weekly_minutes).map(([k, v]) => [String(k), v]),
    )
    exceptions.value = view.exceptions
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const [, feeds, apiTokens, shareLinks] = await Promise.all([
        loadCapacity(),
        api.get<CalendarConnection[]>('/integrations'),
        api.get<ApiToken[]>('/tokens'),
        api.get<ShareLink[]>('/share-links'),
      ])
      integrations.value = feeds
      tokens.value = apiTokens
      links.value = shareLinks
    } catch (e) {
      fail(e, 'Caricamento impostazioni fallito')
    } finally {
      loading.value = false
    }
  }

  // ------------------------------------------------------------ capacità (§11.2)

  /** §11.2: la capacità standard è configurazione, non un evento sul piano —
   *  il ricalcolo passa comunque da una proposal alla prima simulazione. */
  async function saveWeekly(minutes: Record<string, number>) {
    busy.value = true
    error.value = ''
    notice.value = ''
    try {
      await api.put('/capacity/weekly', {
        minutes: Object.fromEntries(Object.entries(minutes).map(([k, v]) => [Number(k), v])),
      })
      await loadCapacity()
      notice.value = 'Capacità settimanale salvata.'
    } catch (e) {
      // L'endpoint di scrittura non esiste ancora lato backend (services/
      // capacity.set_weekly_capacity non è esposto da nessuna rotta): dirlo è
      // più utile che mostrare un "405 Method Not Allowed".
      if (e instanceof ApiError && (e.status === 404 || e.status === 405)) {
        error.value =
          'Il backend non espone ancora PUT /api/capacity/weekly: la capacità base non è modificabile dalla UI.'
      } else fail(e, 'Salvataggio della capacità fallito')
    } finally {
      busy.value = false
    }
  }

  // ------------------------------------------------------------ eccezioni (§11.3)

  /** Ritorna true se la modifica è stata applicata subito, false se è diventata
   *  una proposal da confermare. */
  async function saveException(draft: ExceptionDraft): Promise<boolean> {
    busy.value = true
    error.value = ''
    notice.value = ''
    try {
      const body = { minutes: draft.minutes, kind: draft.kind, note: draft.note || null }
      const result = draft.id
        ? await api.patch<ExceptionOrProposal>(`/capacity/exceptions/${draft.id}`, body)
        : await api.post<ExceptionOrProposal>('/capacity/exceptions', { day: draft.day, ...body })
      return await settle(result)
    } catch (e) {
      fail(e, 'Salvataggio dell\'assenza fallito')
      return false
    } finally {
      busy.value = false
    }
  }

  async function removeException(id: string): Promise<boolean> {
    busy.value = true
    error.value = ''
    notice.value = ''
    try {
      return await settle(await api.del<ExceptionOrProposal>(`/capacity/exceptions/${id}`))
    } catch (e) {
      fail(e, 'Cancellazione dell\'assenza fallita')
      return false
    } finally {
      busy.value = false
    }
  }

  /** §11.3: `proposal` valorizzata = il piano è coinvolto, si chiede conferma. */
  async function settle(result: ExceptionOrProposal): Promise<boolean> {
    if (result.proposal) {
      await proposals.present(result.proposal)
      return false
    }
    await loadCapacity()
    return true
  }

  // ------------------------------------------------------------ integrazioni (§32.18)

  async function addCalendar(name: string, icsUrl: string) {
    busy.value = true
    error.value = ''
    try {
      integrations.value = [
        ...integrations.value,
        await api.post<CalendarConnection>('/integrations/calendars', {
          name, ics_url: icsUrl, enabled: true,
        }),
      ]
    } catch (e) {
      fail(e, 'Aggiunta del calendario fallita')
    } finally {
      busy.value = false
    }
  }

  async function syncCalendar(id: string) {
    busy.value = true
    error.value = ''
    notice.value = ''
    try {
      const result = await api.post<SyncResult>(`/integrations/calendars/${id}/sync`)
      integrations.value = integrations.value.map((c) =>
        c.id === id ? result.connection : c,
      )
      notice.value =
        `Sync completato: ${result.events_upserted} eventi aggiornati, `
        + `${result.events_cancelled} rimossi.`
      // Una riunione nuova riduce la capacità: il piano non cambia da solo (§34).
      if (result.proposal) await proposals.present(result.proposal)
    } catch (e) {
      fail(e, 'Sync fallito')
    } finally {
      busy.value = false
    }
  }

  async function removeCalendar(id: string) {
    busy.value = true
    error.value = ''
    try {
      await api.del(`/integrations/calendars/${id}`)
      integrations.value = integrations.value.filter((c) => c.id !== id)
    } catch (e) {
      fail(e, 'Rimozione del calendario fallita')
    } finally {
      busy.value = false
    }
  }

  // ------------------------------------------------------------ token e link (§28)

  async function createToken(label: string) {
    busy.value = true
    error.value = ''
    try {
      const created = await api.post<ApiTokenCreated>('/tokens', { label, scopes: [] })
      newToken.value = created
      tokens.value = [created, ...tokens.value]
    } catch (e) {
      fail(e, 'Creazione del token fallita')
    } finally {
      busy.value = false
    }
  }

  async function revokeToken(id: string) {
    busy.value = true
    error.value = ''
    try {
      const revoked = await api.del<ApiToken>(`/tokens/${id}`)
      tokens.value = tokens.value.map((t) => (t.id === id ? revoked : t))
      if (newToken.value?.id === id) newToken.value = null
    } catch (e) {
      fail(e, 'Revoca del token fallita')
    } finally {
      busy.value = false
    }
  }

  async function createLink(label: string, kind: 'manager' | 'ics') {
    busy.value = true
    error.value = ''
    try {
      const created = await api.post<ShareLinkCreated>('/share-links', { label, kind })
      newLink.value = created
      links.value = [created, ...links.value]
    } catch (e) {
      fail(e, 'Creazione del link fallita')
    } finally {
      busy.value = false
    }
  }

  async function revokeLink(id: string) {
    busy.value = true
    error.value = ''
    try {
      const revoked = await api.del<ShareLink>(`/share-links/${id}`)
      links.value = links.value.map((l) => (l.id === id ? revoked : l))
      if (newLink.value?.id === id) newLink.value = null
    } catch (e) {
      fail(e, 'Revoca del link fallita')
    } finally {
      busy.value = false
    }
  }

  return {
    weekly, exceptions, integrations, tokens, links, newToken, newLink,
    loading, busy, error, notice,
    weeklyTotal, activeTokens, activeLinks,
    load, loadCapacity, saveWeekly, saveException, removeException,
    addCalendar, syncCalendar, removeCalendar,
    createToken, revokeToken, createLink, revokeLink,
  }
})

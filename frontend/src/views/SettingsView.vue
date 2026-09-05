<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'

import MinutesInput from '../components/MinutesInput.vue'
import ProposalPanel from '../components/ProposalPanel.vue'
import type { CapacityException } from '../api/types'
import {
  EXCEPTION_KINDS,
  WEEKDAYS,
  useSettingsStore,
  type ExceptionDraft,
} from '../stores/settings'
import { hm, iso, longDay } from '../util/time'

/* Impostazioni: capacità base (§11.2), assenze (§11.3), integrazioni (§32.18),
   token API e link manager (§28).

   La cosa che non deve sfuggire: aggiungere ferie su un piano già pianificato
   non applica niente. Il backend risponde con una proposal e la schermata la
   mostra in fondo, con lo stesso before/after del drag & drop. */
const store = useSettingsStore()

// ------------------------------------------------------------ capacità (§11.2)

/** Copia locale: la capacità si salva esplicitamente, non a ogni tasto. */
const weekly = reactive<Record<string, number>>({})
watch(
  () => store.weekly,
  (next) => { for (const d of WEEKDAYS) weekly[d.key] = next[d.key] ?? 0 },
  { immediate: true, deep: true },
)

// ------------------------------------------------------------ assenze (§11.3)

const KIND_LABEL = Object.fromEntries(EXCEPTION_KINDS.map((k) => [k.value, k.label]))
/** Minuti tipici per tipo: ferie = giornata intera via, permesso = mezza. */
const KIND_DEFAULT: Record<string, number> = { VACATION: 0, LEAVE: 240, REDUCED: 240, EXTRA: 120 }

const form = ref(false)
const draft = reactive<ExceptionDraft>({
  id: null, day: iso(new Date()), minutes: 0, kind: 'VACATION', note: '',
})

function openNew() {
  Object.assign(draft, {
    id: null, day: iso(new Date()), minutes: 0, kind: 'VACATION', note: '',
  })
  form.value = true
}

function openEdit(e: CapacityException) {
  Object.assign(draft, {
    id: e.id, day: e.day, minutes: e.minutes, kind: e.kind, note: e.note ?? '',
  })
  form.value = true
}

function onKindChange(kind: string) {
  draft.kind = kind
  if (!draft.id) draft.minutes = KIND_DEFAULT[kind] ?? 0
}

async function submitException() {
  // false = la modifica è diventata una proposal: il pannello in fondo la mostra
  // e il form si chiude comunque, l'intenzione è già stata registrata.
  await store.saveException({ ...draft })
  if (!store.error) form.value = false
}

async function removeException(e: CapacityException) {
  if (!confirm(`Rimuovere ${KIND_LABEL[e.kind] ?? e.kind} del ${longDay(e.day)}?`)) return
  await store.removeException(e.id)
}

// ------------------------------------------------------------ integrazioni

const feed = reactive({ name: '', url: '' })
async function addFeed() {
  if (!feed.name.trim() || !feed.url.trim()) return
  await store.addCalendar(feed.name.trim(), feed.url.trim())
  if (!store.error) { feed.name = ''; feed.url = '' }
}

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString('it-IT') : 'mai'
}

// ------------------------------------------------------------ segreti (§28)

const tokenLabel = ref('')
const linkLabel = ref('')
const linkKind = ref<'manager' | 'ics'>('manager')
const copied = ref('')

async function copy(text: string, what: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = what
  } catch {
    // Clipboard negata (http, permessi): il valore è comunque selezionabile.
    copied.value = ''
    store.error = 'Copia non riuscita: seleziona il testo e copialo a mano.'
  }
}

onMounted(() => store.load())
</script>

<template>
  <section class="settings">
    <header>
      <h1>Impostazioni</h1>
    </header>

    <p v-if="store.error" class="banner danger" role="alert">{{ store.error }}</p>
    <p v-if="store.notice" class="banner ok" role="status">{{ store.notice }}</p>
    <p v-if="store.loading" class="dim">Caricamento…</p>

    <!-- ====================================================== §11.2 capacità -->
    <section class="card block">
      <h2>Capacità settimanale</h2>
      <p class="dim">
        La capacità standard di ogni giorno. Le riunioni e le assenze la riducono:
        qui si imposta il punto di partenza.
      </p>

      <div class="week">
        <MinutesInput
          v-for="d in WEEKDAYS" :key="d.key"
          v-model="weekly[d.key]" :label="d.label"
        />
      </div>

      <div class="foot">
        <span class="dim">
          Totale settimana: <strong>{{ hm(Object.values(weekly).reduce((a, b) => a + b, 0)) }}</strong>
        </span>
        <button class="primary" :disabled="store.busy" @click="store.saveWeekly(weekly)">
          Salva capacità
        </button>
      </div>
    </section>

    <!-- ====================================================== §11.3 assenze -->
    <section class="card block">
      <h2>Ferie, permessi e giornate ridotte</h2>
      <p class="dim">
        Non sono task: cambiano la capacità di un giorno. Se quel giorno ha già
        del lavoro pianificato, la modifica <strong>non viene applicata</strong>:
        genera una proposta da confermare.
      </p>

      <ul v-if="store.exceptions.length" class="list">
        <li v-for="e in store.exceptions" :key="e.id" class="row">
          <div class="info">
            <span class="name">
              {{ longDay(e.day) }}
              <span class="tag">{{ KIND_LABEL[e.kind] ?? e.kind }}</span>
            </span>
            <span class="dim small">
              {{ hm(e.minutes) }} di capacità<template v-if="e.note"> · {{ e.note }}</template>
            </span>
          </div>
          <div class="acts">
            <button @click="openEdit(e)">Modifica</button>
            <button :disabled="store.busy" @click="removeException(e)">Elimina</button>
          </div>
        </li>
      </ul>
      <p v-else class="dim small">Nessuna assenza registrata nei prossimi mesi.</p>

      <form v-if="form" class="form" @submit.prevent="submitException()">
        <label class="field">
          <span class="lab">Giorno</span>
          <!-- Il date picker nativo: già localizzato e accessibile. -->
          <input type="date" v-model="draft.day" :disabled="!!draft.id" required />
        </label>

        <label class="field">
          <span class="lab">Tipo</span>
          <select :value="draft.kind" @change="onKindChange(($event.target as HTMLSelectElement).value)">
            <option v-for="k in EXCEPTION_KINDS" :key="k.value" :value="k.value">{{ k.label }}</option>
          </select>
        </label>

        <MinutesInput v-model="draft.minutes" label="Capacità del giorno" />

        <label class="field wide">
          <span class="lab">Nota</span>
          <input v-model="draft.note" placeholder="facoltativa" />
        </label>

        <div class="acts wide">
          <button type="button" @click="form = false">Annulla</button>
          <button class="primary" type="submit" :disabled="store.busy">
            {{ draft.id ? 'Salva' : 'Aggiungi' }}
          </button>
        </div>
      </form>
      <button v-else @click="openNew()">Aggiungi assenza</button>
    </section>

    <!-- ================================================= §32.18 integrazioni -->
    <section class="card block">
      <h2>Integrazioni calendario</h2>
      <p class="dim">
        Feed ICS in sola lettura. Le riunioni che arrivano da qui riducono la
        capacità disponibile; se il piano ne risente, il sync propone la modifica.
      </p>

      <ul v-if="store.integrations.length" class="list">
        <li v-for="c in store.integrations" :key="c.id" class="row">
          <div class="info">
            <span class="name">
              {{ c.name }}
              <span v-if="!c.enabled" class="tag">Disattivato</span>
              <span v-if="c.last_sync_error" class="tag err">Errore</span>
            </span>
            <span class="dim small url">{{ c.ics_url }}</span>
            <span class="dim small">Ultimo sync: {{ when(c.last_synced_at) }}</span>
            <span v-if="c.last_sync_error" class="err small">{{ c.last_sync_error }}</span>
          </div>
          <div class="acts">
            <button :disabled="store.busy" @click="store.syncCalendar(c.id)">Sincronizza</button>
            <button :disabled="store.busy" @click="store.removeCalendar(c.id)">Rimuovi</button>
          </div>
        </li>
      </ul>
      <p v-else class="dim small">Nessun calendario collegato.</p>

      <form class="form" @submit.prevent="addFeed()">
        <label class="field">
          <span class="lab">Nome</span>
          <input v-model="feed.name" placeholder="Outlook lavoro" required />
        </label>
        <label class="field wide">
          <span class="lab">URL ICS</span>
          <input v-model="feed.url" type="url" placeholder="https://…/calendar.ics" required />
        </label>
        <div class="acts wide">
          <button class="primary" type="submit" :disabled="store.busy">Aggiungi calendario</button>
        </div>
      </form>
    </section>

    <!-- ======================================================== §5.3 token -->
    <section class="card block">
      <h2>Token API</h2>
      <p class="dim">
        Servono a Claude e agli altri client REST. Il valore in chiaro è
        <strong>mostrato una volta sola</strong>: dopo questa schermata non è più
        recuperabile, in database ne resta solo l'hash.
      </p>

      <p v-if="store.newToken" class="secret" role="status">
        <span class="lab">Token di «{{ store.newToken.label }}» — copialo ora, non lo rivedrai</span>
        <code>{{ store.newToken.token }}</code>
        <button @click="copy(store.newToken.token, 'token')">
          {{ copied === 'token' ? 'Copiato ✓' : 'Copia' }}
        </button>
      </p>

      <ul v-if="store.tokens.length" class="list">
        <li v-for="t in store.tokens" :key="t.id" class="row">
          <div class="info">
            <span class="name">
              {{ t.label }}
              <span v-if="t.revoked_at" class="tag">Revocato</span>
            </span>
            <span class="dim small">
              creato {{ when(t.created_at) }} · ultimo uso {{ when(t.last_used_at) }}
            </span>
          </div>
          <div class="acts">
            <button v-if="!t.revoked_at" :disabled="store.busy" @click="store.revokeToken(t.id)">
              Revoca
            </button>
          </div>
        </li>
      </ul>
      <p v-else class="dim small">Nessun token.</p>

      <form class="form" @submit.prevent="tokenLabel.trim() && store.createToken(tokenLabel.trim())">
        <label class="field wide">
          <span class="lab">Etichetta</span>
          <input v-model="tokenLabel" placeholder="Claude desktop" required />
        </label>
        <div class="acts wide">
          <button class="primary" type="submit" :disabled="store.busy">Crea token</button>
        </div>
      </form>
    </section>

    <!-- ==================================================== §5.2 link share -->
    <section class="card block">
      <h2>Link manager e feed ICS</h2>
      <p class="dim">
        Link in sola lettura e revocabili. Anche qui l'URL completo compare una
        volta sola.
      </p>

      <p v-if="store.newLink" class="secret" role="status">
        <span class="lab">Link di «{{ store.newLink.label }}» — copialo ora, non lo rivedrai</span>
        <code>{{ store.newLink.url }}</code>
        <button @click="copy(store.newLink.url, 'link')">
          {{ copied === 'link' ? 'Copiato ✓' : 'Copia' }}
        </button>
      </p>

      <ul v-if="store.links.length" class="list">
        <li v-for="l in store.links" :key="l.id" class="row">
          <div class="info">
            <span class="name">
              {{ l.label }}
              <span class="tag">{{ l.kind === 'ics' ? 'Feed ICS' : 'Manager View' }}</span>
              <span v-if="l.revoked_at" class="tag">Revocato</span>
            </span>
            <span class="dim small">
              creato {{ when(l.created_at) }} · ultimo accesso {{ when(l.last_accessed_at) }}
            </span>
          </div>
          <div class="acts">
            <button v-if="!l.revoked_at" :disabled="store.busy" @click="store.revokeLink(l.id)">
              Revoca
            </button>
          </div>
        </li>
      </ul>
      <p v-else class="dim small">Nessun link.</p>

      <form class="form" @submit.prevent="linkLabel.trim() && store.createLink(linkLabel.trim(), linkKind)">
        <label class="field">
          <span class="lab">Etichetta</span>
          <input v-model="linkLabel" placeholder="Manager" required />
        </label>
        <label class="field">
          <span class="lab">Tipo</span>
          <select v-model="linkKind">
            <option value="manager">Manager View</option>
            <option value="ics">Feed ICS</option>
          </select>
        </label>
        <div class="acts wide">
          <button class="primary" type="submit" :disabled="store.busy">Crea link</button>
        </div>
      </form>
    </section>

    <!-- §11.3: la proposta generata da un'assenza o da un sync si conferma qui. -->
    <ProposalPanel @applied="store.load()" @discarded="store.loadCapacity()" />
  </section>
</template>

<style scoped>
.settings { display: flex; flex-direction: column; gap: 12px; padding: 12px; padding-bottom: 0; }
h1 { margin: 0; font-size: 20px; }
h2 { margin: 0; font-size: 15px; }

.banner { margin: 0; padding: 8px 10px; border-radius: var(--radius); font-size: 13px; }
.banner.danger { background: var(--danger-soft); color: var(--danger); }
.banner.ok { background: var(--accent-soft); color: var(--accent); }

.dim { margin: 0; color: var(--text-dim); font-size: 13px; }
.small { font-size: 12px; }
.err { color: var(--danger); }
.tag.err { background: var(--danger-soft); color: var(--danger); }

.block { padding: 12px; display: flex; flex-direction: column; gap: 10px; }

.week { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.foot { display: flex; flex-direction: column; gap: 8px; }

.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.row {
  display: flex; flex-direction: column; gap: 8px;
  padding: 10px 0; border-top: 1px solid var(--border);
}
.info { display: flex; flex-direction: column; min-width: 0; gap: 2px; }
.name { font-weight: 500; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.url { word-break: break-all; }
.acts { display: flex; gap: 8px; }
.acts button { flex: 1; }

.form {
  display: grid; grid-template-columns: 1fr; gap: 10px;
  padding-top: 10px; border-top: 1px solid var(--border);
}
.field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.lab { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-dim); }

.secret {
  margin: 0; padding: 10px; border-radius: var(--radius);
  background: var(--warning-soft); color: var(--warning);
  display: flex; flex-direction: column; gap: 6px;
}
.secret code {
  background: var(--surface); color: var(--text);
  padding: 8px; border-radius: 6px; font-size: 12px;
  word-break: break-all; user-select: all;
}
.secret button { align-self: flex-start; }

@media (min-width: 768px) {
  .settings { max-width: 900px; }
  .row { flex-direction: row; align-items: center; justify-content: space-between; }
  .acts button { flex: none; min-width: 110px; }
  .foot { flex-direction: row; align-items: center; justify-content: space-between; }
  .form { grid-template-columns: repeat(2, 1fr); align-items: end; }
  .wide { grid-column: 1 / -1; }
  .form .acts { justify-content: flex-end; }
}
</style>

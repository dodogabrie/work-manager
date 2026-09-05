<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { useProjectsStore } from '../stores/projects'
import { hm } from '../util/time'

/* §32.4.6: un progetto è un nome e un colore. Niente di più, perché niente di
   più entra nello scheduler. Per ognuno mostriamo quanto lavoro ci sta sopra:
   è l'unica domanda che si fa davvero da questa schermata. */
const store = useProjectsStore()

const draft = reactive({ name: '', color: '#6b7280' })
const editing = ref<string | null>(null)
const edit = reactive({ name: '', color: '#6b7280' })

async function add() {
  if (!draft.name.trim()) return
  await store.create(draft.name.trim(), draft.color)
  draft.name = ''
}

function startEdit(id: string, name: string, color: string) {
  editing.value = id
  edit.name = name
  edit.color = color
}

async function saveEdit(id: string) {
  if (!edit.name.trim()) return
  await store.update(id, { name: edit.name.trim(), color: edit.color })
  editing.value = null
}

onMounted(() => store.load())
</script>

<template>
  <section class="projects">
    <header>
      <h1>Progetti</h1>
      <p class="sub">
        {{ store.projects.length }} progetti ·
        {{ store.unassigned }} task senza progetto
      </p>
    </header>

    <p v-if="store.error" class="banner" role="alert">{{ store.error }}</p>

    <form class="card new" @submit.prevent="add()">
      <label class="field">
        <span class="lab">Nuovo progetto</span>
        <input v-model="draft.name" placeholder="Nome" required />
      </label>
      <label class="field color">
        <span class="lab">Colore</span>
        <!-- Il color picker nativo: su mobile è quello di sistema, già accessibile. -->
        <input type="color" v-model="draft.color" aria-label="Colore del progetto" />
      </label>
      <button class="primary" type="submit" :disabled="store.busy || !draft.name.trim()">
        Aggiungi
      </button>
    </form>

    <p v-if="store.loading" class="empty">Caricamento…</p>
    <p v-else-if="!store.projects.length" class="empty">Nessun progetto. Creane uno qui sopra.</p>

    <ul v-else class="list">
      <li v-for="p in store.projects" :key="p.id" class="card row" :class="{ off: p.archived }">
        <template v-if="editing === p.id">
          <form class="editing" @submit.prevent="saveEdit(p.id)">
            <input v-model="edit.name" aria-label="Nome del progetto" required />
            <input type="color" v-model="edit.color" aria-label="Colore del progetto" />
            <div class="acts">
              <button type="button" @click="editing = null">Annulla</button>
              <button class="primary" type="submit" :disabled="store.busy">Salva</button>
            </div>
          </form>
        </template>

        <template v-else>
          <span class="swatch" :style="{ background: p.color }" aria-hidden="true"></span>
          <div class="info">
            <span class="name">
              {{ p.name }}
              <!-- Il colore non basta: lo stato archiviato è anche una parola. -->
              <span v-if="p.archived" class="tag">Archiviato</span>
            </span>
            <span class="meta">
              {{ store.statsFor(p.id).tasks }} task ·
              {{ store.statsFor(p.id).openTasks }} apert{{ store.statsFor(p.id).openTasks === 1 ? 'o' : 'i' }} ·
              {{ hm(store.statsFor(p.id).minutes) }} pianificat{{ store.statsFor(p.id).minutes === 60 ? 'a' : 'e' }}
            </span>
          </div>
          <div class="acts">
            <button @click="startEdit(p.id, p.name, p.color)">Modifica</button>
            <button :disabled="store.busy" @click="store.update(p.id, { archived: !p.archived })">
              {{ p.archived ? 'Ripristina' : 'Archivia' }}
            </button>
          </div>
        </template>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.projects { padding: 12px; display: flex; flex-direction: column; gap: 12px; }
h1 { margin: 0; font-size: 20px; }
.sub { margin: 2px 0 0; color: var(--text-dim); font-size: 13px; }

.banner {
  margin: 0; padding: 8px 10px; border-radius: var(--radius);
  background: var(--danger-soft); color: var(--danger); font-size: 13px;
}
.empty { color: var(--text-dim); font-size: 13px; margin: 0; }

.new { display: flex; flex-direction: column; gap: 8px; padding: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.lab { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-dim); }
.color input { width: 64px; padding: 4px; }

.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; flex-wrap: wrap; }
.row.off { opacity: .65; }
.swatch { width: 14px; height: 14px; border-radius: 4px; border: 1px solid var(--border); flex: none; }
.info { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.name { font-weight: 500; display: flex; align-items: center; gap: 6px; }
.meta { font-size: 12px; color: var(--text-dim); }
.acts { display: flex; gap: 8px; }
.acts button { min-width: 44px; }

.editing { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; width: 100%; }
.editing input[type='text'], .editing input:not([type]) { flex: 1; min-width: 160px; }
.editing input[type='color'] { width: 64px; padding: 4px; }

@media (min-width: 768px) {
  .projects { max-width: 800px; }
  .new { flex-direction: row; align-items: flex-end; }
  .new .field:first-child { flex: 1; }
}
</style>

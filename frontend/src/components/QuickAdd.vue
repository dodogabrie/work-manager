<script setup lang="ts">
import { nextTick, ref } from 'vue'

import { usePlanningStore } from '../stores/planning'

/* §6.2: unico campo obbligatorio, il titolo. Su mobile è un FAB in basso a
   destra, dove arriva il pollice. */
const store = usePlanningStore()
const open = ref(false)
const title = ref('')
const field = ref<HTMLInputElement | null>(null)
const saving = ref(false)

async function show() {
  open.value = true
  await nextTick()
  field.value?.focus()
}

async function submit() {
  if (!title.value.trim() || saving.value) return
  saving.value = true
  try {
    await store.quickAdd(title.value.trim())
    title.value = ''
    open.value = false
  } catch {
    // store.error è già impostato: il messaggio lo mostra la schermata.
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <button class="fab" @click="show" aria-label="Aggiungi un task">
    <span aria-hidden="true">＋</span>
  </button>

  <div v-if="open" class="sheet-wrap">
    <div class="scrim" @click="open = false"></div>
    <form class="sheet" @submit.prevent="submit">
      <h2>Nuovo task</h2>
      <label for="qa-title">Titolo</label>
      <input id="qa-title" ref="field" v-model="title" placeholder="Cosa c'è da fare?" />
      <p class="hint">Finisce in Inbox: progetto ed effort si aggiungono dopo.</p>
      <div class="actions">
        <button type="button" @click="open = false">Annulla</button>
        <button type="submit" class="primary" :disabled="!title.trim() || saving">Aggiungi</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.fab {
  position: fixed; right: 16px; z-index: 25;
  bottom: calc(76px + env(safe-area-inset-bottom));  /* sopra la nav mobile */
  width: 56px; height: 56px; min-height: 56px; padding: 0;
  border-radius: 50%;
  background: var(--accent); border-color: var(--accent); color: #fff;
  font-size: 26px; line-height: 1;
  box-shadow: 0 6px 18px rgb(0 0 0 / 22%);
}
.sheet-wrap { position: fixed; inset: 0; z-index: 40; display: flex; flex-direction: column; justify-content: flex-end; }
.scrim { position: absolute; inset: 0; background: rgb(0 0 0 / 40%); }
.sheet {
  position: relative;
  background: var(--surface);
  border-top-left-radius: 16px; border-top-right-radius: 16px;
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
  display: grid; gap: 8px;
}
h2 { margin: 0; font-size: 16px; }
label { font-size: 12px; color: var(--text-dim); }
.hint { margin: 0; font-size: 12px; color: var(--text-dim); }
.actions { display: flex; gap: 8px; }
.actions button { flex: 1; }

@media (min-width: 1024px) {
  .fab { bottom: 24px; }
  .sheet-wrap { justify-content: center; align-items: center; }
  .sheet { width: min(440px, 92vw); border-radius: var(--radius); }
}
</style>

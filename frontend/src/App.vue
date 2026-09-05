<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

/* Navigazione laterale su desktop, barra in basso su mobile (pollice).
   La Manager View e il login non hanno navigazione: sono superfici a sé. */
const route = useRoute()
const chrome = computed(() => !['share', 'login'].includes(String(route.name)))

const items = [
  { to: '/planning', label: 'Planning', icon: '▤' },
  { to: '/inbox', label: 'Inbox', icon: '⊕' },
  { to: '/projects', label: 'Progetti', icon: '◈' },
  { to: '/history', label: 'History', icon: '↺' },
  { to: '/reports', label: 'Report', icon: '⎙' },
  { to: '/settings', label: 'Impostazioni', icon: '⚙' },
]
</script>

<template>
  <div :class="['shell', { bare: !chrome }]">
    <nav v-if="chrome" class="nav" aria-label="Sezioni">
      <RouterLink v-for="i in items" :key="i.to" :to="i.to" class="nav-item">
        <span class="icon" aria-hidden="true">{{ i.icon }}</span>
        <span class="label">{{ i.label }}</span>
      </RouterLink>
    </nav>
    <main class="main"><RouterView /></main>
  </div>
</template>

<style scoped>
.shell { min-height: 100dvh; display: flex; flex-direction: column; }
.main { flex: 1; min-height: 0; }

/* Mobile: barra in basso, etichette piccole sotto l'icona. */
.nav {
  order: 2;
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: space-around;
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
}
.nav-item {
  flex: 1;
  min-height: var(--tap);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 6px 2px;
  text-decoration: none;
  color: var(--text-dim);
}
.nav-item.router-link-active { color: var(--accent); }
.icon { font-size: 18px; line-height: 1; }
.label { font-size: 10px; }

@media (min-width: 1024px) {
  .shell { flex-direction: row; }
  .nav {
    order: 0;
    position: static;
    flex-direction: column;
    justify-content: flex-start;
    width: 200px;
    border-top: none;
    border-right: 1px solid var(--border);
    padding: 12px 8px;
    gap: 2px;
  }
  .nav-item { flex: initial; flex-direction: row; justify-content: flex-start; gap: 10px; padding: 0 12px; border-radius: var(--radius); }
  .nav-item.router-link-active { background: var(--accent-soft); }
  .label { font-size: 14px; }
}
</style>

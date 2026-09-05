import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from './stores/auth'

/* §32.4.6. Planning è il cuore dell'app: tutto il resto è di supporto. */
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/planning' },
    { path: '/planning', name: 'planning', component: () => import('./views/PlanningView.vue') },
    { path: '/inbox', name: 'inbox', component: () => import('./views/InboxView.vue') },
    { path: '/projects', name: 'projects', component: () => import('./views/ProjectsView.vue') },
    { path: '/history', name: 'history', component: () => import('./views/HistoryView.vue') },
    { path: '/reports', name: 'reports', component: () => import('./views/ReportsView.vue') },
    { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue') },
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
    { path: '/share/:token', name: 'share', component: () => import('./views/ManagerView.vue') },
  ],
})

/* Le superfici pubbliche sono solo login e Manager View (§5.2): quest'ultima
   vive di token, non di sessione. Tutto il resto è l'owner application.
   Senza questa guardia una sessione scaduta finisce sulla schermata Planning e
   mostra un errore generico invece di riportare al login. */
const PUBLIC = new Set(['login', 'share'])

router.beforeEach(async (to) => {
  if (PUBLIC.has(String(to.name))) return true

  const auth = useAuthStore()
  if (!auth.checked) await auth.check()
  if (auth.subject) return true

  return { name: 'login', query: { redirect: to.fullPath } }
})

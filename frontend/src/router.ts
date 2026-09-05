import { createRouter, createWebHistory } from 'vue-router'

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

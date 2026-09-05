/* Progetti (§32.4.6). Un progetto è un raggruppamento con un colore: non entra
   nello scheduler, quindi qui nessuna operazione passa da una proposal.

   I conteggi per progetto non hanno un endpoint dedicato: si ricavano dalla
   lista task, che serve comunque una sola volta al caricamento. */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { ApiError, api } from '../api/client'
import type { Project, Task } from '../api/types'

/** Task che non contano nel carico: chiusi o annullati. */
const INACTIVE = new Set(['CANCELLED', 'ARCHIVED', 'DELIVERED'])

export interface ProjectStats {
  tasks: number
  openTasks: number
  minutes: number
}

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<Project[]>([])
  const tasks = ref<Task[]>([])
  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')

  const stats = computed(() => {
    const out = new Map<string, ProjectStats>()
    for (const task of tasks.value) {
      if (!task.project_id) continue
      const row = out.get(task.project_id) ?? { tasks: 0, openTasks: 0, minutes: 0 }
      row.tasks += 1
      if (!INACTIVE.has(task.status)) {
        row.openTasks += 1
        row.minutes += task.planning_effort_minutes
      }
      out.set(task.project_id, row)
    }
    return out
  })

  const unassigned = computed(() => tasks.value.filter((t) => !t.project_id).length)

  function statsFor(id: string): ProjectStats {
    return stats.value.get(id) ?? { tasks: 0, openTasks: 0, minutes: 0 }
  }

  function fail(e: unknown, fallback: string) {
    error.value = e instanceof ApiError ? e.message : fallback
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const [list, allTasks] = await Promise.all([
        api.get<Project[]>('/projects?include_archived=true'),
        api.get<Task[]>('/tasks'),
      ])
      projects.value = list
      tasks.value = allTasks
    } catch (e) {
      fail(e, 'Caricamento dei progetti fallito')
    } finally {
      loading.value = false
    }
  }

  async function create(name: string, color: string) {
    busy.value = true
    error.value = ''
    try {
      const created = await api.post<Project>('/projects', { name, color })
      projects.value = [...projects.value, created].sort((a, b) => a.name.localeCompare(b.name))
    } catch (e) {
      fail(e, 'Creazione del progetto fallita')
    } finally {
      busy.value = false
    }
  }

  async function update(id: string, patch: Partial<Pick<Project, 'name' | 'color' | 'archived'>>) {
    busy.value = true
    error.value = ''
    try {
      const saved = await api.patch<Project>(`/projects/${id}`, patch)
      projects.value = projects.value
        .map((p) => (p.id === id ? saved : p))
        .sort((a, b) => a.name.localeCompare(b.name))
    } catch (e) {
      fail(e, 'Salvataggio del progetto fallito')
    } finally {
      busy.value = false
    }
  }

  return { projects, tasks, loading, busy, error, unassigned, statsFor, load, create, update }
})

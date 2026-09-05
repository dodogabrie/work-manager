import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, api } from '@/api/client'

/** Sessione owner (§5.1). Il cookie è HttpOnly: il frontend non può leggerlo,
 *  quindi l'unico modo di sapere se la sessione è viva è chiedere al backend. */
export const useAuthStore = defineStore('auth', () => {
  const subject = ref<string | null>(null)
  const checked = ref(false)
  const error = ref('')

  async function check(): Promise<boolean> {
    try {
      subject.value = (await api.get<{ subject: string }>('/auth/me')).subject
    } catch {
      subject.value = null
    }
    checked.value = true
    return subject.value !== null
  }

  async function login(password: string): Promise<boolean> {
    error.value = ''
    try {
      subject.value = (
        await api.post<{ subject: string }>('/auth/login', { password })
      ).subject
      checked.value = true
      return true
    } catch (e) {
      // 429 è il rate limit di §28: va distinto da una password sbagliata,
      // altrimenti l'utente riprova all'infinito senza capire perché.
      error.value =
        e instanceof ApiError && e.status === 429
          ? 'Troppi tentativi. Riprova fra un minuto.'
          : 'Password non corretta.'
      return false
    }
  }

  async function logout() {
    await api.post('/auth/logout').catch(() => undefined)
    subject.value = null
  }

  return { subject, checked, error, check, login, logout }
})

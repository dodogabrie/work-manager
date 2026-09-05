<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const password = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  const ok = await auth.login(password.value)
  busy.value = false
  if (ok) router.replace(String(route.query.redirect ?? '/planning'))
  else password.value = ''
}
</script>

<template>
  <div class="wrap">
    <form class="card box" @submit.prevent="submit">
      <h1>Work Planner</h1>
      <label for="pw">Password</label>
      <input
        id="pw"
        v-model="password"
        type="password"
        autocomplete="current-password"
        autofocus
        :aria-invalid="!!auth.error"
        aria-describedby="pw-error"
      />
      <p v-if="auth.error" id="pw-error" class="error" role="alert">{{ auth.error }}</p>
      <button class="primary" type="submit" :disabled="busy || !password">
        {{ busy ? 'Accesso…' : 'Entra' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.wrap { min-height: 100dvh; display: grid; place-items: center; padding: 16px; }
.box { width: 100%; max-width: 340px; padding: 24px; display: grid; gap: 10px; }
h1 { margin: 0 0 8px; font-size: 20px; }
label { font-size: 13px; color: var(--text-dim); }
.error { margin: 0; font-size: 13px; color: var(--danger); }
button { margin-top: 6px; }
</style>

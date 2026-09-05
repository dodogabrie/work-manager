<script setup lang="ts">
import { computed } from 'vue'

/* Gli effort e le capacità sono minuti ovunque (§11.1): questo è l'unico punto
   in cui si scrivono come ore + minuti. Serve otto volte nella schermata
   Impostazioni, quindi vive qui invece che duplicato in ogni campo. */
const props = defineProps<{ modelValue: number; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [number] }>()

const hours = computed(() => Math.floor(props.modelValue / 60))
const mins = computed(() => props.modelValue % 60)

function setHours(value: string) {
  emit('update:modelValue', Math.max(0, Number(value) || 0) * 60 + mins.value)
}
function setMins(value: string) {
  // Oltre i 59 minuti si travasa nelle ore: scrivere "90" in un campo minuti è
  // un'intenzione chiara, non un errore da rifiutare.
  emit('update:modelValue', hours.value * 60 + Math.max(0, Number(value) || 0))
}
</script>

<template>
  <fieldset class="hm">
    <legend>{{ label }}</legend>
    <span class="pair">
      <input
        type="number" min="0" step="1" inputmode="numeric"
        :value="hours" :aria-label="`${label}: ore`"
        @input="setHours(($event.target as HTMLInputElement).value)"
      />
      <span class="unit" aria-hidden="true">h</span>
      <input
        type="number" min="0" step="5" inputmode="numeric"
        :value="mins" :aria-label="`${label}: minuti`"
        @input="setMins(($event.target as HTMLInputElement).value)"
      />
      <span class="unit" aria-hidden="true">m</span>
    </span>
  </fieldset>
</template>

<style scoped>
.hm { border: none; margin: 0; padding: 0; min-width: 0; }
legend {
  padding: 0; font-size: 11px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--text-dim);
}
.pair { display: flex; align-items: center; gap: 4px; }
input { width: 4.5em; text-align: right; }
.unit { color: var(--text-dim); font-size: 13px; }
</style>

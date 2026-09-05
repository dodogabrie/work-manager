import { onScopeDispose, ref, type Ref } from 'vue'

/* matchMedia reattivo: il browser ci dice quando la query cambia, senza
   ricalcolare a ogni pixel di resize. Breakpoint 768/1024 come base.css. */
function media(query: string): Ref<boolean> {
  const mq = window.matchMedia(query)
  const state = ref(mq.matches)
  const update = (e: MediaQueryListEvent) => { state.value = e.matches }
  mq.addEventListener('change', update)
  onScopeDispose(() => mq.removeEventListener('change', update))
  return state
}

export function useBreakpoint() {
  return {
    /** >= 768px: il calendario può essere una griglia a colonne. */
    grid: media('(min-width: 768px)'),
    /** >= 1024px: split coda | planning, niente tab. */
    desktop: media('(min-width: 1024px)'),
  }
}

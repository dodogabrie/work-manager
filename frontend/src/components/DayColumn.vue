<script setup lang="ts">
import { computed } from 'vue'

import type { DayModel } from '../stores/planning'
import { dayLabel, hm } from '../util/time'

/* Una colonna della griglia settimanale (§19): capacità base, meeting,
   assenza, blocchi dei task, capacità residua.

   La colonna ha altezza fissa e i blocchi sono alti in proporzione alla loro
   durata: la giornata si legge a colpo d'occhio invece di dover confrontare
   numeri. La scala è la stessa per tutti i giorni, altrimenti il confronto fra
   giorni — che è il motivo per cui esiste questa vista — non direbbe nulla. */
const props = defineProps<{ day: DayModel }>()

/** Minuti rappresentati a piena altezza: una giornata lavorativa standard. */
const FULL_DAY = 480

const KIND_LABEL: Record<string, string> = {
  VACATION: 'Ferie', LEAVE: 'Permesso', REDUCED: 'Ridotta', EXTRA: 'Extra',
}

/** Capacità del giorno prima delle riunioni: quanto spazio esiste in teoria. */
const baseMinutes = computed(() => props.day.availableMinutes + props.day.meetingMinutes)

/** Minuti sottratti da un'assenza rispetto a una giornata piena (§11.3). */
const unavailableMinutes = computed(() => Math.max(0, FULL_DAY - baseMinutes.value))

/** Un blocco troppo corto non ha spazio per due righe di testo.
 *  90 min -> 54px: sotto questa soglia titolo e sottotitolo non ci stanno e il
 *  testo verrebbe tagliato, quindi si passa alla resa a riga singola. */
function compact(minutes: number): boolean {
  return minutes < 90
}
</script>

<template>
  <div class="col" :class="{ today: day.isToday }">
    <div class="head">
      <span class="date">{{ dayLabel(day.day) }}</span>
      <span class="cap">{{ hm(day.plannedMinutes) }}/{{ hm(day.availableMinutes) }}</span>
    </div>

    <div class="body">
      <div v-if="day.meetingMinutes > 0"
           class="slot meeting"
           :style="{ '--m': day.meetingMinutes }"
           :class="{ compact: compact(day.meetingMinutes) }">
        <span aria-hidden="true">◍</span>
        <span class="label">Riunioni {{ hm(day.meetingMinutes) }}</span>
      </div>

      <div
        v-for="block in day.blocks"
        :key="block.taskId + block.minutes"
        class="slot block"
        :class="{ preview: block.preview, moved: block.moved, compact: compact(block.minutes) }"
        :style="{ '--m': block.minutes, '--project': block.color }"
      >
        <span class="bar" aria-hidden="true"></span>
        <span class="text">
          <span class="title">{{ block.title }}</span>
          <span class="sub">
            <span v-if="block.project">{{ block.project }} · </span>{{ hm(block.minutes) }}
            <span v-if="block.moved" class="mark">· spostato</span>
            <span v-else-if="block.preview" class="mark">· in anteprima</span>
          </span>
        </span>
      </div>

      <!-- Capacità che il giorno non ha: ferie, permesso, giornata ridotta.
           Occupa spazio perché è spazio che non c'è, non spazio libero. -->
      <div v-if="unavailableMinutes > 0"
           class="slot unavailable"
           :style="{ '--m': unavailableMinutes }"
           :class="{ compact: compact(unavailableMinutes) }">
        <span class="label">
          <template v-if="day.exception">
            {{ KIND_LABEL[day.exception.kind] ?? day.exception.kind }}
            <span v-if="day.exception.note">· {{ day.exception.note }}</span>
          </template>
          <template v-else-if="baseMinutes === 0">Non lavorativo</template>
        </span>
      </div>

      <p v-if="!day.blocks.length && day.availableMinutes > 0" class="free">
        Nessun lavoro pianificato
      </p>
    </div>

    <div class="foot" :class="{ over: day.remainingMinutes < 0 }">
      <template v-if="day.remainingMinutes < 0">
        <span aria-hidden="true">▲</span> Oltre capacità di {{ hm(-day.remainingMinutes) }}
      </template>
      <template v-else>Residuo {{ hm(day.remainingMinutes) }}</template>
    </div>
  </div>
</template>

<style scoped>
/* Pixel per minuto: 480 min -> 288px, una colonna che entra in uno schermo
   normale senza scroll verticale. */
.col { --px-per-min: .6; }

.col {
  display: flex; flex-direction: column;
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.col.today { border-color: var(--accent); }
.head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 4px;
  padding: 6px 8px; border-bottom: 1px solid var(--border);
  font-size: 12px;
}
.date { font-weight: 600; text-transform: capitalize; }
.today .date { color: var(--accent); }
.cap { color: var(--text-dim); font-variant-numeric: tabular-nums; }

/* Altezza fissa pari a una giornata piena: lo spazio avanzato in fondo è
   capacità realmente libera, e si vede. */
.body {
  position: relative;
  min-height: calc(480 * var(--px-per-min) * 1px);
  padding: 4px;
  display: flex; flex-direction: column; gap: 3px;
}

.slot {
  height: calc(var(--m) * var(--px-per-min) * 1px);
  /* Sotto i ~22px il testo non è leggibile: meglio un blocco un filo più alto
     del vero che una riga illeggibile. */
  min-height: 22px;
  border-radius: 6px;
  padding: 3px 6px;
  overflow: hidden;
  display: flex; gap: 6px;
  font-size: 12px;
}
.slot.compact { align-items: center; padding-block: 0; }

.meeting { background: var(--meeting-soft); color: var(--meeting); align-items: flex-start; }
.unavailable {
  color: var(--absence);
  border: 1px dashed var(--border);
  background: repeating-linear-gradient(
    -45deg, transparent 0 6px, var(--absence-soft) 6px 12px
  );
  align-items: flex-start;
}
.label { overflow-wrap: anywhere; }

.block { background: var(--surface-2); border: 1px solid transparent; align-items: stretch; }
.bar { width: 4px; border-radius: 2px; background: var(--project); flex: none; }
.text { min-width: 0; display: flex; flex-direction: column; justify-content: center; }
.title { font-size: 13px; line-height: 1.25; overflow-wrap: anywhere; }
.sub { font-size: 11px; color: var(--text-dim); }
.slot.compact .title { font-size: 12px; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
.slot.compact .sub { display: none; }

/* La preview è visivamente distinta dal piano confermato (§13). */
.block.preview { border-style: dashed; border-color: var(--accent); opacity: .85; background: transparent; }
.block.moved { border-style: dashed; border-color: var(--accent); background: var(--accent-soft); }
.mark { color: var(--accent); }

.free { margin: 2px 4px; font-size: 12px; color: var(--text-dim); }
.foot {
  padding: 5px 8px; border-top: 1px solid var(--border);
  font-size: 11px; color: var(--text-dim);
}
.foot.over { color: var(--danger); background: var(--danger-soft); }
</style>

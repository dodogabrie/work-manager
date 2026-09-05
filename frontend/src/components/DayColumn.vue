<script setup lang="ts">
import type { DayModel } from '../stores/planning'
import { dayLabel, hm } from '../util/time'

/* Una colonna della griglia settimanale (§19): capacità base, meeting,
   assenza, blocchi dei task, capacità residua. */
defineProps<{ day: DayModel }>()

const KIND_LABEL: Record<string, string> = {
  VACATION: 'Ferie', LEAVE: 'Permesso', REDUCED: 'Ridotta', EXTRA: 'Extra',
}
</script>

<template>
  <div class="col" :class="{ today: day.isToday }">
    <div class="head">
      <span class="date">{{ dayLabel(day.day) }}</span>
      <span class="cap">{{ hm(day.plannedMinutes) }}/{{ hm(day.availableMinutes) }}</span>
    </div>

    <div class="body">
      <div v-if="day.exception" class="strip absence">
        <span aria-hidden="true">🏖</span>
        {{ KIND_LABEL[day.exception.kind] ?? day.exception.kind }}
        <span v-if="day.exception.note">· {{ day.exception.note }}</span>
      </div>
      <div v-if="day.meetingMinutes > 0" class="strip meeting">
        <span aria-hidden="true">◍</span> Riunioni {{ hm(day.meetingMinutes) }}
      </div>

      <div
        v-for="block in day.blocks"
        :key="block.taskId + block.minutes"
        class="block"
        :class="{ preview: block.preview, moved: block.moved }"
        :style="{ '--project': block.color }"
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

      <p v-if="!day.blocks.length && !day.exception && day.availableMinutes > 0" class="free">
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
.body { flex: 1; padding: 6px; display: flex; flex-direction: column; gap: 6px; }

.strip {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; padding: 4px 6px; border-radius: 6px;
}
.absence { background: var(--absence-soft); color: var(--absence); }
.meeting { background: var(--meeting-soft); color: var(--meeting); }

.block {
  display: flex; gap: 6px; align-items: stretch;
  padding: 5px 6px; border-radius: 6px;
  background: var(--surface-2);
  border: 1px solid transparent;
}
.bar { width: 4px; border-radius: 2px; background: var(--project); flex: none; }
.text { min-width: 0; display: flex; flex-direction: column; }
.title { font-size: 13px; overflow-wrap: anywhere; }
.sub { font-size: 11px; color: var(--text-dim); }
/* La preview è visivamente distinta dal piano confermato (§13). */
.block.preview { border-style: dashed; border-color: var(--accent); opacity: .85; background: transparent; }
.block.moved { border-style: dashed; border-color: var(--accent); background: var(--accent-soft); }
.mark { color: var(--accent); }

.free { margin: 0; font-size: 12px; color: var(--text-dim); }
.foot {
  padding: 5px 8px; border-top: 1px solid var(--border);
  font-size: 11px; color: var(--text-dim);
}
.foot.over { color: var(--danger); background: var(--danger-soft); }
</style>

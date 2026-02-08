<script setup lang="ts">
import { computed } from 'vue'

interface TimelineAnomaly {
  id: string
  metric: string
  agent: string
  value: number
  unit: string
  deviation: string
  severity: 'critical' | 'warning' | 'info'
  time: string
  timestamp: number
}

const props = defineProps<{
  title: string
  anomalies: TimelineAnomaly[]
  startTime: number
  endTime: number
}>()

const emit = defineEmits<{
  'anomaly-click': [anomaly: TimelineAnomaly]
}>()

const timelineMarkers = computed(() => {
  const markers = []
  const duration = props.endTime - props.startTime
  for (let i = 0; i <= 4; i++) {
    const time = new Date(props.startTime + (duration / 4) * i)
    markers.push(time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }))
  }
  return markers
})

function getPosition(timestamp: number) {
  const duration = props.endTime - props.startTime
  return ((timestamp - props.startTime) / duration) * 100
}

function getSeverityColor(severity: string) {
  switch (severity) {
    case 'critical': return 'bg-red-500'
    case 'warning': return 'bg-yellow-500'
    case 'info': return 'bg-blue-500'
    default: return 'bg-slate-400'
  }
}
</script>

<template>
  <div class="card p-6">
    <h3 class="text-lg font-medium text-slate-900 dark:text-white mb-4">{{ title }}</h3>
    
    <div class="relative h-20 bg-slate-100 dark:bg-slate-900 rounded-lg">
      <!-- Time markers -->
      <div class="absolute bottom-0 left-0 right-0 flex justify-between px-2 text-xs text-slate-400">
        <span v-for="(marker, i) in timelineMarkers" :key="i">{{ marker }}</span>
      </div>
      
      <!-- Anomaly dots -->
      <div
        v-for="anomaly in anomalies"
        :key="anomaly.id"
        :style="{ left: `${getPosition(anomaly.timestamp)}%` }"
        class="absolute top-1/2 transform -translate-x-1/2 -translate-y-1/2 cursor-pointer group"
        @click="emit('anomaly-click', anomaly)"
      >
        <div :class="['w-4 h-4 rounded-full', getSeverityColor(anomaly.severity)]"></div>
        <div class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
          {{ anomaly.metric }}: {{ anomaly.value }}{{ anomaly.unit }} ({{ anomaly.deviation }})
        </div>
      </div>
      
      <!-- Empty state -->
      <div v-if="anomalies.length === 0" class="absolute inset-0 flex items-center justify-center">
        <p class="text-slate-400 text-sm">No anomalies in this time range</p>
      </div>
    </div>
  </div>
</template>

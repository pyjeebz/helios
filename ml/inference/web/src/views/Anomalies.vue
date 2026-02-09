<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ExclamationTriangleIcon, ArrowPathIcon } from '@heroicons/vue/24/outline'
import EmptyState from '@/components/common/EmptyState.vue'
import Badge from '@/components/common/Badge.vue'
import AnomalyTimeline from '@/components/charts/AnomalyTimeline.vue'
import api, { mlApi, type AnomalyResponse, type Anomaly as ApiAnomaly } from '@/services/api'

const severityFilter = ref('all')
const timeRange = ref('1h')
const loading = ref(false)
const error = ref<string | null>(null)
let refreshInterval: number | null = null

interface DisplayAnomaly {
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

const detectedAnomalies = ref<DisplayAnomaly[]>([])

const timeRanges = [
  { value: '1h', label: 'Last 1 hour', hours: 1 },
  { value: '24h', label: 'Last 24 hours', hours: 24 },
  { value: '7d', label: 'Last 7 days', hours: 168 },
  { value: '30d', label: 'Last 30 days', hours: 720 }
]

// Fetch metrics and detect anomalies
const detectAnomalies = async () => {
  loading.value = true
  error.value = null
  
  try {
    const selectedRange = timeRanges.find(r => r.value === timeRange.value) || timeRanges[1]
    const metricsToCheck = ['cpu_utilization', 'memory_utilization']
    
    // Fetch metric data for each metric
    const metricsData: Record<string, { timestamp: string; value: number }[]> = {}
    
    for (const metricName of metricsToCheck) {
      try {
        const response = await api.get(`/metrics/${metricName}`, {
          params: { hours: selectedRange.hours, limit: 100 }
        })
        if (response.data.data?.length) {
          metricsData[metricName] = response.data.data.map((d: any) => ({
            timestamp: d.timestamp,
            value: d.value
          }))
        }
      } catch (e) {
        console.warn(`No data for ${metricName}`)
      }
    }
    
    if (Object.keys(metricsData).length === 0) {
      detectedAnomalies.value = []
      return
    }
    
    // Call anomaly detection API
    const response = await mlApi.detect({
      metrics: metricsData,
      threshold_sigma: 2.5
    })
    
    // Transform API response to display format
    detectedAnomalies.value = response.anomalies.map((a: ApiAnomaly, idx: number) => {
      const timestamp = new Date(a.timestamp).getTime()
      const now = Date.now()
      const diffMs = now - timestamp
      const diffMin = Math.floor(diffMs / 60000)
      const diffHour = Math.floor(diffMin / 60)
      
      let timeAgo: string
      if (diffMin < 60) timeAgo = `${diffMin}m ago`
      else if (diffHour < 24) timeAgo = `${diffHour}h ago`
      else timeAgo = `${Math.floor(diffHour / 24)}d ago`
      
      const severity = a.severity === 'high' || a.severity === 'critical' ? 'critical' 
        : a.severity === 'medium' ? 'warning' : 'info'
      
      return {
        id: String(idx),
        metric: a.metric,
        agent: 'system',
        value: a.value * 100,
        unit: '%',
        deviation: `${(a.score ?? 0) > 0 ? '+' : ''}${(a.score ?? 0).toFixed(1)}σ`,
        severity,
        time: timeAgo,
        timestamp
      }
    })
    
  } catch (e: any) {
    console.error('Anomaly detection failed:', e)
    error.value = e.response?.data?.detail || e.message || 'Detection failed'
  } finally {
    loading.value = false
  }
}

const filteredAnomalies = computed(() => {
  if (severityFilter.value === 'all') return detectedAnomalies.value
  return detectedAnomalies.value.filter(a => a.severity === severityFilter.value)
})

const timelineStartTime = computed(() => {
  const range = timeRanges.find(r => r.value === timeRange.value)
  return Date.now() - (range?.hours || 24) * 3600000
})
const timelineEndTime = computed(() => Date.now())

const handleAnomalyClick = (anomaly: DisplayAnomaly) => {
  console.log('Anomaly clicked:', anomaly)
}

onMounted(() => {
  detectAnomalies()
  // Auto-refresh every hour
  refreshInterval = window.setInterval(detectAnomalies, 3600000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-slate-900 dark:text-white">Anomalies</h1>
        <p class="text-slate-500 dark:text-slate-400">
          Detected anomalies in your infrastructure metrics
        </p>
      </div>
      
      <div class="flex items-center gap-2">
        <select v-model="severityFilter" class="input w-40">
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
        <select v-model="timeRange" @change="detectAnomalies" class="input w-40">
          <option v-for="range in timeRanges" :key="range.value" :value="range.value">
            {{ range.label }}
          </option>
        </select>
        <button @click="detectAnomalies" :disabled="loading" class="btn-secondary flex items-center gap-2">
          <ArrowPathIcon :class="['w-4 h-4', loading && 'animate-spin']" />
          Refresh
        </button>
      </div>
    </div>
    
    <!-- Error Alert -->
    <div v-if="error" class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
      <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    </div>
    
    <!-- Loading State -->
    <div v-if="loading" class="card p-12 text-center">
      <ArrowPathIcon class="w-8 h-8 mx-auto text-slate-400 animate-spin mb-4" />
      <p class="text-slate-500">Analyzing metrics for anomalies...</p>
    </div>
    
    <!-- Anomaly Timeline -->
    <AnomalyTimeline
      v-else-if="filteredAnomalies.length > 0"
      :title="`Anomaly Timeline (${timeRanges.find(r => r.value === timeRange)?.label})`"
      :anomalies="filteredAnomalies"
      :start-time="timelineStartTime"
      :end-time="timelineEndTime"
      @anomaly-click="handleAnomalyClick"
    />
    
    <!-- Empty State -->
    <EmptyState
      v-if="!loading && detectedAnomalies.length === 0"
      title="No anomalies detected"
      description="Great news! No anomalies have been detected in your infrastructure. We'll alert you when something unusual is found."
      :icon="ExclamationTriangleIcon"
    />
    
    <!-- Anomalies Table -->
    <div v-if="!loading && filteredAnomalies.length > 0" class="card">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-slate-50 dark:bg-slate-900">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Severity
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Agent
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Metric
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Value
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Deviation
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Time
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-200 dark:divide-slate-700">
            <tr 
              v-for="anomaly in filteredAnomalies" 
              :key="anomaly.id"
              class="hover:bg-slate-50 dark:hover:bg-slate-900/50 cursor-pointer"
              @click="handleAnomalyClick(anomaly)"
            >
              <td class="px-6 py-4 whitespace-nowrap">
                <Badge :variant="anomaly.severity === 'critical' ? 'error' : anomaly.severity">
                  {{ anomaly.severity }}
                </Badge>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                {{ anomaly.agent }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">
                {{ anomaly.metric }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium" :class="anomaly.severity === 'critical' ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-white'">
                {{ (anomaly.value ?? 0).toFixed(1) }}{{ anomaly.unit }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">
                {{ anomaly.deviation }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">
                {{ anomaly.time }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
